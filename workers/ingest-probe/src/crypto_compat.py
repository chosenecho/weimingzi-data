"""Expose Pyodide's upstream PyCryptodome under zoku's expected namespace."""

import sys
import importlib
import importlib.util


def defer_crypto():
    """Defer real crypto modules used only by login/refresh, never stub them.

    zoku eagerly imports these even for public reads. Loading their FFI handles
    only on first attribute access avoids putting handles in a Worker snapshot.
    """
    for name in (
        "Cryptodome.Cipher.PKCS1_OAEP",
        "Cryptodome.Cipher.PKCS1_v1_5",
        "Cryptodome.Hash.SHA256",
        "Cryptodome.PublicKey.RSA",
        "Cryptodome.PublicKey.ECC",
    ):
        if name in sys.modules:
            continue
        spec = importlib.util.find_spec(name)
        if spec is None or spec.loader is None:
            raise ImportError(name)
        loader = importlib.util.LazyLoader(spec.loader)
        spec.loader = loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        parent, attribute = name.rsplit(".", 1)
        setattr(importlib.import_module(parent), attribute, module)
        loader.exec_module(module)


def install():
    if sys.platform == "emscripten":
        import Crypto

        sys.modules.setdefault("Cryptodome", Crypto)
        defer_crypto()
