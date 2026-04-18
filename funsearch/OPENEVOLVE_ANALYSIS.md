# OpenEvolve Interface Analysis

All paths below are relative to `openevolve_vendor/` unless noted. Line numbers are indicative (clone HEAD at time of writing). Package has ~9.6k LOC.

---

## 1. Entry Point and Run Configuration

### Entry points (three layers)

**Shell script** — `openevolve-run.py`
```python
from openevolve.cli import main
main()
```

**CLI** — `openevolve/cli.py::main()` (argparse)
```
openevolve-run.py INITIAL_PROGRAM EVAL_FILE
    [--config CONFIG.yaml]
    [--output OUTPUT_DIR]
    [--iterations N]          # overrides config.max_iterations
    [--target-score FLOAT]    # stop early when best >= target
    [--checkpoint PATH]       # resume from a checkpoints/checkpoint_N/ dir
    [--api-base URL]          # overrides config.llm.api_base
    [--primary-model NAME]    # overrides config.llm.models[0].name
    [--secondary-model NAME]  # overrides config.llm.models[1].name
    [--log-level LEVEL]
```
Flow: `load_config(args.config)` → override primary/secondary via `config.llm.update_model_params(...)` + `config.llm.rebuild_models()` → `OpenEvolve(initial_program, eval_file, config=config, output_dir=...)` → `await openevolve.run(iterations, target_score, checkpoint_path)`.

**Programmatic API** — `openevolve/api.py`
```python
def run_evolution(
    initial_program: str | Path,           # path or inline code
    evaluator: Callable | str | Path,      # callable or path to .py with evaluate()
    config: Config | dict | str | None = None,
    iterations: int | None = None,
    output_dir: str | None = None,
    cleanup: bool = True,
) -> EvolutionResult

def evolve_function(func, test_cases, iterations=100, **kwargs) -> EvolutionResult
def evolve_algorithm(algorithm_class, benchmark, iterations=100, **kwargs) -> EvolutionResult
def evolve_code(initial_code, evaluator, iterations=100, **kwargs) -> EvolutionResult

@dataclass
class EvolutionResult:
    best_program: Program | None
    best_score: float
    best_code: str
    metrics: Dict[str, float]
    output_dir: str | None
```
`_prepare_evaluator` (same file) serialises a callable into a self-contained module that exposes `def evaluate(program_path)` — lets you hand it a plain Python function.

**Controller class** — `openevolve/controller.py::OpenEvolve`
```python
class OpenEvolve:
    def __init__(
        self,
        initial_program_path: str,
        evaluation_file: str,
        config_path: str | None = None,
        config: Config | None = None,
        output_dir: str | None = None,
    )
    async def run(
        self,
        iterations: int | None = None,
        target_score: float | None = None,
        checkpoint_path: str | None = None,
    ) -> Program | None
```
In `__init__`: builds `LLMEnsemble(config.llm.models)`, secondary `LLMEnsemble(config.llm.evaluator_models)`, `PromptSampler(config.prompt)`, `ProgramDatabase(config.database)`, `Evaluator(config.evaluator, evaluation_file, llm_evaluator_ensemble, evaluator_prompt_sampler, database, suffix)`. Delegates the loop to `ProcessParallelController` (`openevolve/process_parallel.py`) when `parallel_evaluations > 1`.

**Fresh-start guard (important for injection)** — in `controller.run`:
```python
should_add_initial = (start_iteration == 0 and len(self.database.programs) == 0)
```
→ The initial program is only added when the DB is empty. Pre-seeded programs survive.

### Configuration (YAML → dataclasses)

Top-level — `openevolve/config.py::Config`
```python
@dataclass
class Config:
    llm: LLMConfig
    prompt: PromptConfig
    database: DatabaseConfig
    evaluator: EvaluatorConfig
    evolution_trace: EvolutionTraceConfig
    max_iterations: int = 10000
    checkpoint_interval: int = 100
    language: str = "python"
    file_suffix: str = ".py"
    diff_based_evolution: bool = True
    max_code_length: int = 10000
    diff_pattern: str = r"<<<<<<< SEARCH\n(.*?)=======\n(.*?)>>>>>>> REPLACE"
    early_stopping_patience: int | None = None
    convergence_threshold: float = 0.001
    early_stopping_metric: str = "combined_score"
    max_tasks_per_child: int | None = None
    random_seed: int | None = None
    log_level: str = "INFO"
    log_dir: str | None = None

    @classmethod
    def from_yaml(cls, path: str) -> "Config": ...

def load_config(config_path: str | None) -> Config: ...
```
- `${VAR}` in `api_key` is expanded from the environment.
- See `configs/default_config.yaml` for a filled example (defaults to Gemini OpenAI-compat at `https://generativelanguage.googleapis.com/v1beta/openai/`).
- `configs/island_config_example.yaml` shows `primary_model`/`secondary_model` backward-compat form.

---

## 2. Evaluation Interface

User file is an importable Python module (path passed as `evaluation_file`). Loaded via `importlib.util.spec_from_file_location`. **Required:** a module-level `def evaluate(program_path: str)`.

### Minimal signature
```python
def evaluate(program_path: str) -> Dict[str, float]
# or
def evaluate(program_path: str) -> EvaluationResult
```

### Rich return type — `openevolve/evaluation_result.py`
```python
@dataclass
class EvaluationResult:
    metrics: Dict[str, float]
    artifacts: Dict[str, str | bytes] = field(default_factory=dict)
```
If a dict is returned it is wrapped. `metrics` is what MAP-Elites sees; include raw numeric values for any custom `feature_dimensions` (the DB does min-max scaling + binning itself — **do not pre-bin**).

### Special keys
- `combined_score` — if present, used as fitness by `utils/metrics_utils.py::get_fitness_score`. Otherwise fitness = mean of numeric metrics excluding `error` and `feature_dimensions`.
- `error` — string, triggers failure handling.
- Any key named in `config.database.feature_dimensions` is *excluded* from fitness and used as a MAP-Elites axis.

### Cascade evaluation — `openevolve/evaluator.py::Evaluator._cascade_evaluate`
Optional module-level hooks, run in order:
```python
def evaluate_stage1(program_path) -> Dict[str, float] | EvaluationResult
def evaluate_stage2(program_path) -> Dict[str, float] | EvaluationResult
def evaluate_stage3(program_path) -> Dict[str, float] | EvaluationResult
```
Advances only if `_passes_threshold(metrics, config.evaluator.cascade_thresholds[i])` — uses `combined_score` if present, else numeric mean excluding `"error"`. Thresholds default `[0.5, 0.75, 0.9]`. Controlled by `config.evaluator.cascade_evaluation: bool`.

### Runtime
- Code written to a temp file with `config.file_suffix`, path passed as arg.
- Run in a thread executor with `asyncio.wait_for(timeout=config.evaluator.timeout)` (default 300 s).
- Retried up to `config.evaluator.max_retries` (3) on exception.
- `get_pending_artifacts(program_id)` pops the artifact dict so the DB can persist it separately from metrics.

---

## 3. Program Database Interface

File: `openevolve/database.py` (~2.5k LOC, class `ProgramDatabase`).

### The `Program` dataclass
```python
@dataclass
class Program:
    id: str
    code: str
    changes_description: str = ""
    language: str = "python"
    parent_id: str | None = None
    generation: int = 0
    timestamp: float = field(default_factory=time.time)
    iteration_found: int = 0
    metrics: Dict[str, float] = field(default_factory=dict)
    complexity: float = 0.0         # auto-computed from len(code)
    diversity: float = 0.0          # auto-computed vs reference set
    metadata: Dict[str, Any] = field(default_factory=dict)   # {"island": int, "migrant": bool, ...}
    prompts: Dict[str, Any] | None = None
    artifacts_json: str | None = None
    artifact_dir: str | None = None
    embedding: List[float] | None = None
```

### Core methods
```python
class ProgramDatabase:
    def __init__(self, config: DatabaseConfig)

    # Write
    def add(self, program: Program, iteration: int | None = None,
            target_island: int | None = None) -> str
    def store_artifacts(self, program_id: str, artifacts: Dict[str, str | bytes]) -> None
    def log_prompt(self, program_id: str, template_key: str, prompt: dict, responses: list) -> None

    # Read
    def get(self, program_id: str) -> Program | None
    def get_best_program(self, metric: str | None = None) -> Program | None
    def get_top_programs(self, n: int = 10, metric: str | None = None,
                         island_idx: int | None = None) -> List[Program]
    def get_artifacts(self, program_id: str) -> Dict[str, str | bytes]

    # Sample (what the controller uses each iteration)
    def sample(self, num_inspirations: int = 5) -> Tuple[Program, List[Program]]
    def sample_from_island(self, island_id: int, num_inspirations: int = 5
                           ) -> Tuple[Program, List[Program]]   # thread-safe, no state mutation

    # Islands / MAP-Elites
    def migrate_programs(self) -> None
    def should_migrate(self) -> bool
    def set_current_island(self, island_id: int) -> None
    def next_island(self) -> None
    def increment_island_generation(self) -> None
    def get_island_stats(self) -> List[dict]
    def log_island_status(self) -> None

    # Persistence
    def save(self, path: str, iteration: int | None = None) -> None
    def load(self, path: str) -> None
```

### Selection policy
`sample_from_island` draws parent with three buckets:
- `rand < exploration_ratio` → random program in that island
- `< exploration_ratio + exploitation_ratio` → random from archive (elite)
- else → fitness-weighted choice from the island

`_sample_inspirations(parent, n)` — from the parent's island only: island best + top `n * elite_selection_ratio` + nearby feature cells + random fill.

### Placement
`add` runs:
1. Optional novelty rejection (embedding cosine + optional LLM judge — see `DatabaseConfig.novelty_llm`, `similarity_threshold`).
2. `_calculate_feature_coords` — built-in dims: `complexity` (code length), `diversity` (cached against 20-program reference set), `score` (fitness). Custom dims: read from `program.metrics[dim]`, min-max scaled via `_update_feature_stats` + `_scale_feature_value`, then `bin_idx = int(scaled * num_bins)`.
3. Place in `island_feature_maps[island][coord_key]`, replacing if `_is_better(new, existing)`.
4. Update archive + best tracker + enforce population limit (`_enforce_population_limit` removes worst by fitness, never `best_program_id` or the excluded).

### Fitness
`openevolve/utils/metrics_utils.py::get_fitness_score(metrics, feature_dimensions)`:
- `metrics["combined_score"]` if present.
- Else average of non-feature, non-NaN numeric metrics.
- Falls back to `safe_numeric_average(metrics)` if no non-feature metrics exist (back-compat).

---

## 4. Prompt Builder

### `PromptSampler` — `openevolve/prompt/sampler.py`
```python
class PromptSampler:
    def __init__(self, config: PromptConfig)
    def build_prompt(
        self,
        current_program: str,
        parent_program: str,
        program_metrics: dict,
        previous_programs: list[Program],
        top_programs: list[Program],
        inspirations: list[Program] = None,
        language: str = "python",
        evolution_round: int = 0,
        diff_based_evolution: bool = True,
        template_key: str | None = None,
        program_artifacts: dict | None = None,
        feature_dimensions: list[str] | None = None,
        current_changes_description: str = "",
        **kwargs,
    ) -> Dict[str, str]   # {"system": ..., "user": ...}

    def set_templates(self, system_template: str, user_template: str) -> None
```
Template selection precedence: explicit `template_key` arg > `self.user_template_override` > `"diff_user"` / `"full_rewrite_user"` based on `diff_based_evolution`.

### `TemplateManager` — `openevolve/prompt/templates.py`
```python
class TemplateManager:
    def __init__(self, custom_template_dir: str | None = None)
    def get_template(self, name: str) -> str
    def get_fragment(self, name: str, **kwargs) -> str
    def add_template(self, name: str, template: str) -> None
    def add_fragment(self, name: str, fragment: str) -> None
```
Cascading load:
1. `openevolve/prompts/defaults/*.txt` + `fragments.json`
2. Overridden by files in `config.prompt.template_dir` (if set).

Template names used by defaults: `system_message`, `evaluator_system_message`, `diff_user`, `full_rewrite_user`, `evolution_history`, `previous_attempt`, `top_program`, `inspirations_section`, `inspiration_program`, `evaluation`.

### PromptConfig knobs (selected)
- `template_dir: str | None` — override directory
- `system_message`, `evaluator_system_message` — literal overrides (take priority over files)
- `num_top_programs: int = 3`, `num_diverse_programs: int = 2`
- `use_template_stochasticity: bool`, `template_variations: dict` — A/B fragments
- `include_artifacts: bool`, `max_artifact_bytes: int = 20_000`, `artifact_security_filter: bool`
- `programs_as_changes_description: bool`
- `suggest_simplification_after_chars: 500`, `include_changes_under_chars: 100`
- `concise_implementation_max_lines: 10`, `comprehensive_implementation_min_lines: 50`
- `diff_summary_max_line_len`, `diff_summary_max_lines`

---

## 5. Island / MAP-Elites Configuration

`DatabaseConfig` (in `openevolve/config.py`):
```python
db_path: str | None
in_memory: bool = True
log_prompts: bool = False

population_size: int = 1000
archive_size: int = 100

num_islands: int = 5
elite_selection_ratio: float = 0.1
exploration_ratio: float = 0.2
exploitation_ratio: float = 0.7

feature_dimensions: List[str] = ["complexity", "diversity"]
feature_bins: int | Dict[str, int] = 10          # per-dim override supported
diversity_reference_size: int = 20

migration_interval: int = 50                      # in *generations*, not iterations
migration_rate: float = 0.1

random_seed: int | None

# Artifacts
artifacts_base_path: str | None
artifact_size_threshold: int = 32_768             # small → JSON in-DB; large → file on disk
cleanup_old_artifacts: bool = True
artifact_retention_days: int = 30
max_snapshot_artifacts: int = 100

# Novelty
novelty_llm: str | None
embedding_model: str | None
similarity_threshold: float = 0.99
```

### Feature coordinates — `_calculate_feature_coords(program)`
- Built-in: `"complexity"` → `len(code)`; `"diversity"` → fast-cached diversity vs reference set of 20; `"score"` → fitness.
- Custom dim named `X` → reads `program.metrics[X]` raw value; min-max scales against observed range; bins into `feature_bins[X]`.
- **Never** pre-compute bin indices in your evaluator; send raw continuous values.

### Migration — `migrate_programs()`
- Ring topology: migrants flow to `(i+1) % N` and `(i-1) % N`.
- Skips programs with `metadata["migrant"] == True` (prevents re-migration).
- Creates a *copy* with `metadata={..., "island": target_island, "migrant": True}`.

### Triggering
`should_migrate()` returns `True` when `max(island_generations) - last_migration_generation >= migration_interval`.

### Culling
`_enforce_population_limit(exclude_program_id)` evicts the worst-by-fitness programs when `len(programs) > population_size`. Never removes `best_program_id` or `exclude_program_id`. Elites in the archive are protected separately.

---

## 6. LLM Ensemble

### Config — `openevolve/config.py::LLMConfig`
```python
@dataclass
class LLMModelConfig:
    api_base: str | None = None
    api_key: str | None = None                    # supports ${ENV_VAR}
    name: str = "gpt-4o-mini"
    init_client: Callable[[LLMModelConfig], LLMInterface] | None = None   # hook
    weight: float = 1.0
    system_message: str | None = None
    temperature: float = 0.7
    top_p: float = 0.95
    max_tokens: int = 4096
    timeout: int = 60
    retries: int = 3
    retry_delay: int = 5
    random_seed: int | None = None
    reasoning_effort: str | None = None
    manual_mode: bool = False                     # file-based human-in-the-loop

@dataclass
class LLMConfig(LLMModelConfig):
    models: List[LLMModelConfig] = field(default_factory=list)
    evaluator_models: List[LLMModelConfig] = field(default_factory=list)
    # Backward-compat single-model form (converted to models=[..., ...]):
    primary_model: str | None = None
    primary_model_weight: float = 0.8
    secondary_model: str | None = None
    secondary_model_weight: float = 0.2

    def rebuild_models(self) -> None            # call after mutating primary/secondary
    def update_model_params(self, params: dict) -> None   # propagate shared fields
```

YAML shape:
```yaml
llm:
  api_base: https://...
  api_key: ${OPENAI_API_KEY}
  models:
    - name: gpt-4o
      weight: 0.7
      temperature: 0.8
    - name: gpt-4o-mini
      weight: 0.3
  evaluator_models:
    - name: gpt-4o-mini
      weight: 1.0
```

### Runtime — `openevolve/llm/ensemble.py::LLMEnsemble`
```python
class LLMEnsemble:
    def __init__(self, models_cfg: List[LLMModelConfig])
    async def generate(self, prompt: str) -> str
    async def generate_with_context(self, system_message: str, messages: list[dict]) -> str
    async def generate_multiple(self, prompt: str, n: int) -> list[str]
    async def parallel_generate(self, prompts: list[str]) -> list[str]
    async def generate_all_with_context(self, system_message, messages) -> list[str]  # every model
```
Client construction per model: `model_cfg.init_client(model_cfg)` if provided, else `OpenAILLM(model_cfg)` (`openevolve/llm/openai.py`, uses `openai.OpenAI(api_key, base_url, timeout, max_retries)`). Weights normalised; `_sample_model()` uses `random.choices(..., weights=self.weights, k=1)`.

### Manual mode
`LLMModelConfig.manual_mode=True` writes prompt JSON to a queue dir and polls for `*.answer.json` — human-in-the-loop. See `openevolve/llm/openai.py`.

---

## 7. Diff vs Full-Rewrite Mode

### Switch
`config.diff_based_evolution: bool = True` (top-level `Config`).

### Diff mode
- Prompt: `DIFF_USER_TEMPLATE` (`openevolve/prompt/templates.py`) — instructs the LLM to emit SEARCH/REPLACE blocks:
```
<<<<<<< SEARCH
# old code (must match exactly)
=======
# new code
>>>>>>> REPLACE
```
- Parse: `openevolve/utils/code_utils.py::extract_diffs(text, config.diff_pattern)` → `[(search, replace), ...]`.
- Apply: `apply_diff_blocks(original_text, blocks) -> (new_text, applied_count)` (line-wise exact match).
- Pattern regex: `config.diff_pattern = r"<<<<<<< SEARCH\n(.*?)=======\n(.*?)>>>>>>> REPLACE"`.
- Respects `# EVOLVE-BLOCK-START` / `# EVOLVE-BLOCK-END` markers — see `parse_evolve_blocks`. When blocks exist, diffs/rewrites are constrained to their contents.

### Full-rewrite mode
- Prompt: `FULL_REWRITE_USER_TEMPLATE` — asks for complete code in a ```<language>``` block.
- Parse: `parse_full_rewrite(llm_response, language)` — matches ```<language>\n(.*?)```, falls back to any ``` fence, then to raw text.
- Used by non-Python languages (e.g., `examples/llm_prompt_optimization/config.yaml` sets `language: "text"` + `diff_based_evolution: false`).

---

## 8. Injection API (external seeding of scored programs)

**There is no HTTP/RPC endpoint.** All injection is in-process via the database. Two supported paths:

### Path A — construct controller, seed DB, then run
```python
from openevolve import OpenEvolve, Config
from openevolve.database import Program
import uuid, time

controller = OpenEvolve(
    initial_program_path="initial.py",
    evaluation_file="evaluator.py",
    config=Config.from_yaml("cfg.yaml"),
    output_dir="out/",
)

for island_id in range(controller.database.config.num_islands):
    for code, metrics, artifacts in my_external_programs(island_id):
        p = Program(
            id=str(uuid.uuid4()),
            code=code,
            language=controller.config.language,
            generation=0,
            timestamp=time.time(),
            iteration_found=0,
            metrics=metrics,                        # must include combined_score or feature dims
            metadata={"island": island_id, "source": "external_seed"},
        )
        controller.database.add(p, iteration=0, target_island=island_id)
        if artifacts:
            controller.database.store_artifacts(p.id, artifacts)

await controller.run(iterations=N)
```
The fresh-start guard (`controller.py`):
```python
should_add_initial = (start_iteration == 0 and len(self.database.programs) == 0)
```
ensures your seeded programs aren't clobbered by the initial program on a cold start.

### Path B — write checkpoint files and load
1. Write each program as JSON into `<ckpt_dir>/programs/<id>.json` matching `Program.to_dict()`/`Program.from_dict()` layout.
2. Write `<ckpt_dir>/metadata.json` with `islands`, `island_feature_maps`, `archive`, `best_program_id`, `island_best_programs`, `last_iteration`, `feature_stats`.
3. Start with `controller.run(checkpoint_path="<ckpt_dir>")` — `ProgramDatabase.load(path)` rehydrates.

### During a run
`ProgramDatabase.add(program, iteration=..., target_island=...)` is the only sanctioned mutation path — it handles novelty checks, feature-coord binning, island placement, archive updates, best-program tracking and population cap. Bypassing it (e.g. poking `database.programs` directly) skips all of that.

### Artifacts
`ProgramDatabase.store_artifacts(program_id, {"stdout": "...", "plot.png": b"..."})`:
- ≤ `artifact_size_threshold` (32 KB default) → stored inline as JSON on the `Program`.
- larger → file on disk under `artifacts_base_path/<program_id>/`.

### Feature-coord caveat
If your seeded programs carry custom `feature_dimensions`, the raw metric value is required (the DB handles min-max scaling + binning itself). Pre-computed bin indices break the scale.

---

## Appendix: Key files

| Concern | Path |
|---|---|
| CLI | `openevolve/cli.py` |
| Public API | `openevolve/api.py`, `openevolve/__init__.py` |
| Controller | `openevolve/controller.py` |
| Iteration worker | `openevolve/iteration.py`, `openevolve/process_parallel.py` |
| Database | `openevolve/database.py` |
| Evaluator | `openevolve/evaluator.py`, `openevolve/evaluation_result.py` |
| Prompts | `openevolve/prompt/sampler.py`, `openevolve/prompt/templates.py`, `openevolve/prompts/defaults/` |
| LLM | `openevolve/llm/ensemble.py`, `openevolve/llm/openai.py`, `openevolve/llm/base.py` |
| Config | `openevolve/config.py` |
| Utils | `openevolve/utils/code_utils.py`, `openevolve/utils/metrics_utils.py` |
| Example configs | `configs/default_config.yaml`, `configs/island_config_example.yaml` |
| Example eval | `examples/function_minimization/evaluator.py` |
| Template override example | `examples/llm_prompt_optimization/config.yaml` |
