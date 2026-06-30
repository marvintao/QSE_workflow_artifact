Definition of configuration prioritization:

- **Given**:

    - $FM$ attributed feature model is a set of $n \in \mathbb{N}$ features $FM = \{x_1, \cdots, x_n\}$ and each feature $x_i$ contains an attribute $a_i$ with $i \in [1,n]$
    - $fc \subseteq FM$ a configuration is a set of selected features
    - $C(fc): fc \mapsto r \in \mathbb{R}$ cost function calculating the cost $r$ of a configuration $fc$ over the attributes $a_j$ of features $\{x_j |x_j \in fc\}, j \le n$
    - $m \in \mathbb{N}$ number of searched configurations

- **Goal**:

    Find the optimal sequence of $m$ valid configurations $[fc_{0}, \cdots,  fc_{m}]$ according to $FM$, in which configurations are sorted by optimality in accordance with $C(fc): C(fc_{i}) \le C(fc_{j}), i < j$, and $i, j \in [0,𝑚]$.