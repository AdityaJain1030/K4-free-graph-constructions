import networkx as nx
import numpy as np

adj = np.array([
  [0,0,0,1,1,0,1,1,0,0],
  [0,0,0,0,0,1,1,0,1,1],
  [0,0,0,0,0,1,0,1,1,1],
  [1,0,0,0,1,0,1,1,0,0],
  [1,0,0,1,0,0,0,0,1,1],
  [0,1,1,0,0,0,0,1,1,0],
  [1,1,0,1,0,0,0,0,0,1],
  [1,0,1,1,0,1,0,0,0,0],
  [0,1,1,0,1,1,0,0,0,0],
  [0,1,1,0,1,0,1,0,0,0]
])

G = nx.from_numpy_array(adj)

# All vertices should have identical local neighborhoods up to isomorphism
neighborhoods = []
for v in G.nodes():
    subg = G.subgraph(G.neighbors(v))
    neighborhoods.append(nx.weisfeiler_lehman_graph_hash(subg))

print("All neighborhoods isomorphic:", len(set(neighborhoods)) == 1)

# Check vertex transitivity
aut = nx.algorithms.isomorphism.vf2userfunc.DiGraphMatcher
print("Is regular:", nx.is_regular(G))
print("Is vertex transitive:", nx.is_vertex_transitive(G))  # requires networkx 3.3+

# Alternatively check via automorphism group acting on vertices
import networkx.algorithms.graph_hashing as gh
print("Degree sequence:", sorted(G.degree(), key=lambda x: x[1]))
print("Is strongly regular:", nx.is_strongly_regular(G))