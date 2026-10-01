"""Minimal Streamlit API stand-in for smoke tests (records rendering; NOT a browser)."""
import contextlib, functools

class StopScript(Exception): pass
class RerunScript(Exception): pass

class _State(dict):
    __getattr__ = lambda s, k: s[k] if k in s else (_ for _ in ()).throw(AttributeError(k))
    def __setattr__(s, k, v): s[k] = v
    def __delattr__(s, k): del s[k]
session_state = _State()
LOG = []          # rendered things
CFG = {"submit": set(), "buttons": set(), "text": {}}   # test-controlled inputs

class _Ctx:
    def __enter__(s): return s
    def __exit__(s,*a): return False
    def __getattr__(s, name): return globals()[name]
def _ctx(*a, **k): return _Ctx()
def _cols(spec, **k):
    n = spec if isinstance(spec, int) else len(spec)
    return [_Ctx() for _ in range(n)]
def _rec(kind):
    def f(*a, **k): LOG.append((kind, a[0] if a else None)); return None
    return f
def set_page_config(**k): LOG.append(("page_config", k.get("page_title")))
markdown = _rec("markdown"); caption = _rec("caption"); error = _rec("error"); success = _rec("success"); info = _rec("info")
warning = _rec("warning"); title=_rec("title"); dataframe=_rec("dataframe"); plotly_chart=_rec("chart"); balloons=_rec("balloons")
page_link = _rec("page_link"); download_button=_rec("dl"); code=_rec("code"); write=_rec("write"); subheader=_rec("sub"); header=_rec("header")
columns = _cols
def tabs(labels): return [_Ctx() for _ in labels]
container = expander = popover = form = _ctx
sidebar = _Ctx()
def slider(label, lo=0, hi=100, value=None, step=None, key=None, **k):
    v = session_state.get(key, value) if key else value
    return v
def text_input(label, value="", key=None, **k):
    return CFG["text"].get(key, value)
selectbox = lambda label, options, index=0, key=None, **k: options[index]
multiselect = lambda label, options, default=None, **k: default if default is not None else []
number_input = lambda label, value=0, **k: value
checkbox = lambda label, value=False, **k: value
def metric(label, value, *a, **k): LOG.append(("metric", (label, value)))
def form_submit_button(label, **k): return label in CFG["submit"] or any(s in label for s in CFG["submit"])
def button(label, key=None, **k): return (key in CFG["buttons"]) or (label in CFG["buttons"])
def stop(): raise StopScript()
def rerun(): raise RerunScript()
def switch_page(p): LOG.append(("switch_page", p)); raise RerunScript()
def cache_resource(*a, **k):
    if a and callable(a[0]): return functools.lru_cache(None)(a[0])
    return lambda f: functools.lru_cache(None)(f)
cache_data = cache_resource
class _QP(dict): pass
query_params = _QP()
def __getattr__(name):     # anything else: harmless no-op
    return _rec(name)

import sys, types
__path__ = []
_c = types.ModuleType("streamlit.components"); _v1 = types.ModuleType("streamlit.components.v1")
_c.__path__ = []; _v1.html = _rec("html"); _v1.declare_component = lambda *a, **k: (lambda **kw: None); _c.v1 = _v1
sys.modules["streamlit.components"] = _c; sys.modules["streamlit.components.v1"] = _v1
components = _c

def fragment(*a, **k):
    if a and callable(a[0]): return a[0]
    return lambda f: f

radio = lambda label, options, index=0, key=None, **k: CFG.get("radio", {}).get(key, options[index] if index is not None else None)
select_slider = lambda label, options=(), value=None, **k: value if value is not None else list(options)[0]
segmented_control = pills = lambda label, options, default=None, **k: default
file_uploader = lambda *a, **k: None
date_input = lambda label, value=None, **k: value
time_input = lambda label, value=None, **k: value
text_area = lambda label, value="", **k: value
toggle = lambda label, value=False, **k: value
chat_input = lambda *a, **k: None
chat_message = spinner = status = empty = _ctx
class _CC:
    def __getattr__(self, n): return lambda *a, **k: None
column_config = _CC()
data_editor = lambda df, **k: df
