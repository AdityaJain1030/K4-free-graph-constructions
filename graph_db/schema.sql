CREATE TABLE IF NOT EXISTS cache (
    graph_id                TEXT    NOT NULL,
    source                  TEXT    NOT NULL,
    n                       INTEGER NOT NULL,
    m                       INTEGER NOT NULL,
    density                 REAL    NOT NULL,
    d_min                   INTEGER NOT NULL,
    d_max                   INTEGER NOT NULL,
    d_avg                   REAL    NOT NULL,
    d_var                   REAL    NOT NULL,
    degree_sequence         TEXT    NOT NULL,
    is_regular              INTEGER NOT NULL,
    regularity_d            INTEGER,
    is_connected            INTEGER NOT NULL,
    n_components            INTEGER NOT NULL,
    diameter                INTEGER,
    radius                  INTEGER,
    edge_connectivity       INTEGER,
    vertex_connectivity     INTEGER,
    girth                   INTEGER,
    n_triangles             INTEGER NOT NULL,
    avg_clustering          REAL    NOT NULL,
    assortativity           REAL,
    clique_num              INTEGER NOT NULL,
    greedy_chromatic_bound  INTEGER NOT NULL,
    is_k4_free              INTEGER NOT NULL,
    eigenvalues_adj         TEXT    NOT NULL,
    spectral_radius         REAL    NOT NULL,
    spectral_gap            REAL,
    n_distinct_eigenvalues  INTEGER NOT NULL,
    eigenvalues_lap         TEXT    NOT NULL,
    algebraic_connectivity  REAL,
    alpha                   INTEGER NOT NULL,
    c_log                   REAL,
    beta                    REAL,
    turan_density           REAL    NOT NULL,
    codegree_avg            REAL,
    codegree_max            INTEGER,
    mis_vertices            TEXT    NOT NULL,
    triangle_edges          TEXT    NOT NULL,
    triangle_vertices       TEXT    NOT NULL,
    high_degree_vertices    TEXT    NOT NULL,
    metadata                TEXT    NOT NULL DEFAULT '{}',
    PRIMARY KEY (graph_id, source)
);

CREATE INDEX IF NOT EXISTS idx_source   ON cache(source);
CREATE INDEX IF NOT EXISTS idx_n        ON cache(n);
CREATE INDEX IF NOT EXISTS idx_c_log    ON cache(c_log);
CREATE INDEX IF NOT EXISTS idx_alpha    ON cache(alpha);
CREATE INDEX IF NOT EXISTS idx_d_max    ON cache(d_max);
CREATE INDEX IF NOT EXISTS idx_is_k4    ON cache(is_k4_free);
CREATE INDEX IF NOT EXISTS idx_regular  ON cache(is_regular);
CREATE INDEX IF NOT EXISTS idx_codeg_max ON cache(codegree_max);
