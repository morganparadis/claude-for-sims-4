---
name: verify-game-hooks
description: Before monkey-patching or registering a callback against a game's internal API (Sims 4, Unity mods, KSP, etc.), verify the invocation-site signature by decompiling. Prevents silent-swallow errors from mismatched arg shapes, wrong class inheritance, or hooked-method-doesn't-fire failures.
---

# Verify game hooks before writing them

Games silently swallow callback errors. A wrong monkey-patch signature or wrong method choice fails invisibly — no exception, no crash, just "the hook doesn't seem to fire." You then rebuild, restart the game, retest, get nothing, and blame the wrong layer.

This skill exists because in the Llamafone Sims 4 mod, I:
- Hooked `PlayerPlannedDramaNode._run` and `.cleanup` (internal lifecycle methods) — didn't fire for dinner parties. Correct hook was `BaseDramaNode.add_callback_on_complete_func` (public callback list).
- Wrote `_on_complete(node)` when the engine calls `_callbacks_on_complete(self, from_shutdown=<bool>)`. `TypeError: got unexpected keyword 'from_shutdown'` was swallowed silently — no log line, no user-visible error, hook appeared "installed" but recorded nothing.

Each mistake cost a rebuild + restart + in-game repro cycle. Verifying upfront takes ~5 minutes and eliminates the class of bug entirely.

## When to use this skill

Any time you write code that:
- Monkey-patches a method on a game class (`SomeClass.method = _patched`)
- Registers a callback with a game API (`obj.add_callback_on_X(fn)`, `service.register(...)`, `event.subscribe(...)`)
- Overrides a virtual/instance method by inheritance in a way you didn't verify

Skip if:
- The hook target is documented (real docs, not "someone's Discord message")
- You've verified it works in this exact game patch already
- The game is well-known enough that Stack Overflow / GitHub issues confirm the signature

## The checklist

**1. Find the hook target's DEFINITION site.**
The `.pyc` for the class you're hooking. In Sims 4 that's inside `simulation.zip` / `core.zip` / `base.zip` under `Data/Simulation/Gameplay/`. Extract with `unzip`, decompile with the game's bundled Python (matches the `.pyc` magic number). For Sims 4:

```bash
unzip -o "/path/to/simulation.zip" 'drama_scheduler/drama_node.pyc' -d /tmp/decompile/
tools/python37/python.exe _dump_cb.py /tmp/decompile/drama_scheduler/drama_node.pyc
```

The `_dump_cb.py` helper (recreate if missing — 15 lines using `marshal.load` + printing `co_names`/`co_consts`) shows the class's methods and internal names.

**2. Confirm the METHOD you're hooking is actually the right one.**

Grep the target class's `co_names` for:
- Public API methods (usually named `add_callback_X`, `register_Y`, or the event name itself like `on_loading_screen_animation_finished`)
- Callable-list attributes (`_callbacks_on_*` — these are `CallableList` objects; you register into them with the matching `add_callback_on_X_func` method)

If you find TWO candidates — one that looks like public API and one that's a lifecycle internal like `_run` / `_setup` — favor the public API. Internal lifecycle methods may be called for some subclasses but not others, or may not fire for all event types.

**3. Decompile the INVOCATION SITE to get the exact signature.**

This is the step I keep skipping. Find where the callback / hooked method gets CALLED, not just defined. For a callable list, look at the class method that INVOKES the list:

```bash
# Example: I registered into _callbacks_on_complete. Where does the engine invoke it?
tools/python37/python.exe _dump_method.py /tmp/decompile/drama_scheduler/drama_node.pyc complete
```

Read the disassembly for `LOAD_ATTR '_callbacks_on_complete'` followed by `CALL_*`. The `CALL_FUNCTION_KW` bytecode's tuple constant lists the keyword arg names. Positional args come from `LOAD_FAST` between the callable and the call.

Example finding for `BaseDramaNode.complete`:
```
LOAD_FAST                'self'
LOAD_ATTR                '_callbacks_on_complete'
LOAD_FAST                'self'
LOAD_FAST                'from_shutdown'
LOAD_CONST               ('from_shutdown',)
CALL_FUNCTION_KW         2
```

Translation: `self._callbacks_on_complete(self, from_shutdown=from_shutdown)`. Callback receives one positional + one kwarg.

**4. Match the callback signature EXACTLY, or absorb everything with `*args`/`**kwargs`.**

Two safe patterns:

```python
# Exact match (self-documenting, catches unexpected changes across patches)
def _on_complete(node, from_shutdown=False):
    ...

# Absorb-everything (survives new args added in future patches)
def _on_complete(node, *args, **kwargs):
    ...
```

Never write `def _on_complete(node):` unless you've verified the engine ONLY passes one positional arg.

**5. Add success logging to the callback.**

At least one `_log(...)` call inside the callback so you can visually confirm it fired at runtime. Without this, "hook doesn't work" and "hook fires but does nothing" look identical in the log — and one is a lot easier to fix than the other.

```python
def _on_complete(node, *args, **kwargs):
    try:
        # ...actual work...
        _log(f"RECORDED complete on {type(node).__name__}: uid={getattr(node, 'uid', '?')}")
    except Exception as e:
        _log(f"_on_complete failed on {type(node).__name__}: {type(e).__name__}: {e}")
```

Strip / gate behind a debug flag before shipping if the log line would fire too often.

**6. Test with the LOG open in a tail before assuming a hook works.**

`tail -f Documents/Llamafone_Log.txt` (or equivalent) while you trigger the game action. If nothing appears in the log for that specific test:
- Check for install lines (`installed X hook`) — is the patch even applied this session?
- Check for skip messages inside the callback — did filter logic reject it?
- Check for `handler failed` — did the callback raise?

Silent absence = usually one of: wrong method hooked, wrong callback signature, wrong game patch, mod not reloaded (Sims 4 caches modules at launch — full quit + relaunch required).

## Common gotchas

- **Sims 4 caches modules at launch.** Changing the `.ts4script` on disk does nothing until the game is fully quit and relaunched. Verify version-string logs on module reload to confirm your new code is actually loaded.

- **Internal lifecycle methods (`_run`, `_setup`, `cleanup`) don't fire for every subclass.** Some subclasses override without calling `super()`. Prefer callable-list registration on the base class.

- **`CallableList.__call__` swallows exceptions from individual callbacks silently.** Wrapping your callback body in `try/except _log(...)` is the ONLY way to see if it's blowing up.

- **`_callbacks_on_X` might be attached per-instance, not per-class.** If so, patching `SomeClass._setup` to register your callback on `self` is the right shape (not patching a class-level attribute). Verify by checking whether `_callbacks_on_complete` is initialized in `__init__` or as a class attribute.

- **Callback signatures can differ across game patches.** Use `*args, **kwargs` unless you have a strong reason to enforce exact matching.

## Anti-pattern to avoid

Do NOT do this:

```python
# WRONG: assumes signature, no verification, no logging
def install_hook():
    from some.game.module import SomeClass
    SomeClass._some_method = _patched
    return True

def _patched(self):
    do_stuff(self)
```

Do this instead:

```python
# RIGHT: verified against decompilation, absorb-signature, success + failure logging
def install_hook():
    """Monkey-patch SomeClass._some_method. Verified against
    game_module.pyc on patch 2026-06-17: engine invokes
      self._some_method(self, foo, bar=<int>)
    """
    from some.game.module import SomeClass
    if getattr(SomeClass, "_llamafone_hooked", False):
        return True
    original = SomeClass._some_method
    def _patched(self, *args, **kwargs):
        result = original(self, *args, **kwargs)
        try:
            do_stuff(self)
            _log(f"hook fired on {type(self).__name__}")
        except Exception as e:
            _log(f"hook handler failed: {type(e).__name__}: {e}")
        return result
    SomeClass._some_method = _patched
    SomeClass._llamafone_hooked = True
    _log(f"installed hook on {SomeClass.__name__}._some_method")
    return True
```

## Decompile helpers (Sims 4)

Keep these two scripts around (they're gitignored but reusable):

**`_dump_cb.py`** — show a class's methods + constants:
```python
import marshal, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
with open(sys.argv[1], 'rb') as f:
    f.read(16); code = marshal.load(f)
print("co_names:", code.co_names)
for c in code.co_consts:
    if hasattr(c, 'co_name'):
        print(f"  <code {c.co_name}>")
        print(f"    co_names: {c.co_names}")
        print(f"    co_consts: {[x for x in c.co_consts if not hasattr(x, 'co_name')]}")
```

**`_dump_method.py`** — disassemble a specific method:
```python
import marshal, sys, dis, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
target = sys.argv[2]
with open(sys.argv[1], 'rb') as f:
    f.read(16); code = marshal.load(f)
def walk(co):
    if hasattr(co, 'co_name') and co.co_name == target:
        print(f"=== {co.co_name} ===")
        print(f"argcount: {co.co_argcount}")
        print(f"co_varnames[:argcount]: {co.co_varnames[:co.co_argcount]}")
        print(f"co_names:  {co.co_names}")
        print("--- dis ---")
        for ins in dis.get_instructions(co):
            print(f"  {ins.opname:24} {ins.argval!r}")
    if hasattr(co, 'co_consts'):
        for c in co.co_consts:
            if hasattr(c, 'co_name'):
                walk(c)
walk(code)
```

Usage:
```bash
tools/python37/python.exe _dump_cb.py /tmp/decompile/some_class.pyc
tools/python37/python.exe _dump_method.py /tmp/decompile/some_class.pyc method_name
```

The Python 3.7 interpreter at `tools/python37/python.exe` is required — the game's `.pyc` files use Python 3.7 marshal format, and marshaling breaks across Python versions.
