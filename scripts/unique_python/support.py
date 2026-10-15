"""Shared authoring algorithms, embedded in the isolated reference runner."""
COMMON = '''
def _flow(n, edges, s, t):
    capacity=[[0]*n for _ in range(n)]
    for a,b,c in edges: capacity[a][b]+=c
    total=0
    while True:
        parent=[-1]*n; parent[s]=s; q=deque([s])
        while q and parent[t]<0:
            u=q.popleft()
            for v in range(n):
                if capacity[u][v]>0 and parent[v]<0: parent[v]=u; q.append(v)
        if parent[t]<0: return total
        amount=math.inf; v=t
        while v!=s: u=parent[v]; amount=min(amount,capacity[u][v]); v=u
        v=t
        while v!=s: u=parent[v]; capacity[u][v]-=amount; capacity[v][u]+=amount; v=u
        total+=amount

def _floyd(n, edges, directed=True):
    d=[[math.inf]*n for _ in range(n)]
    for i in range(n): d[i][i]=0
    for a,b,w in edges:
        d[a][b]=min(d[a][b],w)
        if not directed: d[b][a]=min(d[b][a],w)
    for k in range(n):
        for i in range(n):
            for j in range(n): d[i][j]=min(d[i][j],d[i][k]+d[k][j])
    return d

def _components(n, edges):
    g=[[] for _ in range(n)]; rev=[[] for _ in range(n)]
    for a,b in edges: g[a].append(b); rev[b].append(a)
    seen=set(); order=[]
    def visit(u):
        seen.add(u)
        for v in g[u]:
            if v not in seen: visit(v)
        order.append(u)
    for u in range(n):
        if u not in seen: visit(u)
    labels=[-1]*n; count=0
    def collect(u):
        labels[u]=count
        for v in rev[u]:
            if labels[v]<0: collect(v)
    for u in reversed(order):
        if labels[u]<0: collect(u); count+=1
    return count,labels
'''
