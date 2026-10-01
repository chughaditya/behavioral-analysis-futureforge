class _Any:
    def __init__(self,*a,**k): pass
    def __getattr__(self,n): return lambda *a,**k: None
Figure=Indicator=Scatter=Bar=Pie=Heatmap=Histogram=Box=Scatterpolar=_Any
