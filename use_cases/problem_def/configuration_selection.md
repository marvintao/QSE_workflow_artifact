Definition of configuration selection:

- **Given**:

    - $FM$ attributed feature model is a set of $n \in \mathbb{N}$ features $FM = \{x_1, \cdots, x_n\}$ and each feature $x_i$ contains an attribute $a_i$ with $i \in [1,n]$
    - $fc \subseteq FM$ a configuration is a set of selected features
    - $C(fc): fc \mapsto r \in \mathbb{R}$ cost function calculating the cost $r$ of a configuration $fc$ over the attributes $a_j$ of features $\{x_j |x_j \in fc\}, j \le n$

- **Goal**:

    Find a valid configuration according to $FM$ that is optimal regarding $C(fc)$ with $fc \in FC$, where $FC$ is the set all possible configurations.