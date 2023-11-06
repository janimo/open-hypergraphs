from typing import List
from dataclasses import dataclass
from open_hypergraphs.finite_function import FiniteFunction, DTYPE
from open_hypergraphs.hypergraph import *

@dataclass
class OpenHypergraph(HasHypergraph):
    """ An OpenHypergraph is a cospan in Hypergraph whose feet are discrete. """
    s: FiniteFunction
    t: FiniteFunction
    H: Hypergraph

    def __post_init__(self):
        if self.s.dtype != self.t.dtype or self.t.dtype != self.H.dtype:
            raise ValueError("dtypes of all components must be the same")

    @property
    def dtype(self):
        return self.s.dtype

    @property
    def source(self):
        return self.s >> self.H.w

    @property
    def target(self):
        return self.t >> self.H.w

    def signature(self):
        return self.H.w.to_initial(), self.H.x.to_initial()

    @classmethod
    def identity(cls, w, x, dtype=DTYPE):
        if x.source != 0:
            raise ValueError(f"x.source must be 0, but was {x.source}")
        s = t = cls.FiniteFunction().identity(w.source, dtype=dtype)
        H = cls.Hypergraph().discrete(w, x, dtype=dtype)
        return cls(s, t, H)

    def compose(f: 'OpenHypergraph', g: 'OpenHypergraph'):
        assert f.target == g.source
        h = f @ g
        q = f.t.inject0(g.H.W).coequalizer(g.s.inject1(f.H.W))
        return type(f)(
            s = f.s.inject0(g.H.W) >> q,
            t = g.t.inject1(f.H.W) >> q,
            H = h.H.coequalize_vertices(q))

    def __rshift__(f: 'OpenHypergraph', g: 'OpenHypergraph') -> 'OpenHypergraph':
        return f.compose(g)

    ##############################
    # Symmetric monoidal structure

    @classmethod
    def unit(cls, w, x, dtype=DTYPE):
        """ The empty open hypergraph; the monoidal unit ``OpenHypergraph.unit : I → I`` """
        assert len(w) == 0
        assert len(x) == 0
        e = cls.FiniteFunction().initial(0, dtype=dtype)
        return cls(e, e, cls.Hypergraph().empty(w, x, dtype=dtype))

    def unit_of(self):
        """ Given an OpenHypergraph, return the unit over the same signature """
        dtype = self.s.table.dtype
        return type(self).unit(self.H.w.to_initial(), self.H.x.to_initial(), dtype=dtype)

    def tensor(f: 'OpenHypergraph', g: 'OpenHypergraph') -> 'OpenHypergraph':
        return type(f)(
            s = f.s @ g.s,
            t = f.t @ g.t,
            H = f.H + g.H)

    def __matmul__(f: 'OpenHypergraph', g: 'OpenHypergraph') -> 'OpenHypergraph':
        return f.tensor(g)

    @classmethod
    def twist(cls, a: FiniteFunction, b: FiniteFunction, x: FiniteFunction, dtype=DTYPE) -> 'OpenHypergraph':
        if len(x) != 0:
            raise ValueError(f"twist(a, b, x) must have len(x) == 0, but len(x) == {len(x)}")
        s = cls.FiniteFunction().twist(len(a), len(b), dtype=dtype)
        t = cls.FiniteFunction().identity(len(a) + len(b), dtype=dtype)
        # NOTE: because the twist is in the source map, the type of the wires in
        # this hypergraph is b + a instead of a + b! (this matters!)
        H = cls.Hypergraph().discrete(b + a, x, dtype=dtype)
        return cls(s, t, H)

    ##############################
    # Frobenius

    def dagger(self):
        return type(self)(self.t, self.s, self.H)

    @classmethod
    def spider(cls, s: FiniteFunction, t: FiniteFunction, w: FiniteFunction, x: FiniteFunction, dtype=None) -> 'OpenHypergraph':
        dtype = dtype or s.table.dtype
        H = cls.Hypergraph().discrete(w, x, dtype=dtype)
        return cls(s, t, H)

    @classmethod
    def half_spider(cls, s: FiniteFunction, w: FiniteFunction, x: FiniteFunction, dtype=None) -> 'OpenHypergraph':
        dtype = dtype or s.table.dtype
        t = cls.FiniteFunction().identity(len(w))
        return cls.spider(s, t, w, x, dtype)

    @classmethod
    def singleton(cls, x: FiniteFunction, a: FiniteFunction, b: FiniteFunction, dtype=None) -> 'OpenHypergraph':
        """ Given FiniteFunctions ``a : A → Σ₀`` and ``b : B → Σ₀`` and an
        operation ``x : 1 → Σ₁``, create an open hypergraph with a single
        operation ``x`` with type ``A → B``. """
        if len(x) != 1:
            raise ValueError(f"len(x) must be 1, but was {len(x)}")

        if a.target != b.target:
            raise ValueError(f"a and b must have same target, but a.target == {a.target} and b.target == {b.target}")

        s = cls.FiniteFunction().inj0(len(a), len(b), dtype)
        t = cls.FiniteFunction().inj1(len(a), len(b), dtype)
        H = cls.Hypergraph()(
            s = cls.IndexedCoproduct().singleton(s, dtype),
            t = cls.IndexedCoproduct().singleton(t, dtype),
            w = a + b,
            x = x)

        return cls(s, t, H)

    ##############################
    # List operations

    @classmethod
    def tensor_operations(cls, x: FiniteFunction, a: IndexedCoproduct, b: IndexedCoproduct, dtype=DTYPE) -> 'OpenHypergraph':
        """ The N-fold tensoring of operations ``x``. Like 'singleton' but for many operations.

            x : N → Σ₁
            a : N → Σ₀*
            b : N → Σ₀*
        """
        if b.values.target != a.values.target or b.values.table.dtype != a.values.table.dtype:
            raise ValueError("a and b must have the same target and dtype")
        w = a.values.to_initial()

        if len(x) != len(a) or len(x) != len(b):
            raise ValueError("must have len(x) == len(a) == len(b)")

        s = cls.FiniteFunction().inj0(len(a.values), len(b.values), dtype=dtype)
        t = cls.FiniteFunction().inj1(len(a.values), len(b.values), dtype=dtype)
        H = cls.Hypergraph()(
            s = cls.IndexedCoproduct()(sources=a.sources, values=s),
            t = cls.IndexedCoproduct()(sources=b.sources, values=t),
            w = a.values + b.values,
            x = x)

        return cls(s, t, H)

    @classmethod
    def tensor_list(cls, ds: List['OpenHypergraph'], wn=None, xn=None) -> 'OpenHypergraph':
        raise NotImplementedError("TODO")

class HasOpenHypergraph(HasHypergraph):
    @classmethod
    @abstractmethod
    def OpenHypergraph(cls) -> Type[OpenHypergraph]:
        ...

    @classmethod
    def Hypergraph(cls) -> Type[Hypergraph]:
        return cls.OpenHypergraph().Hypergraph()
