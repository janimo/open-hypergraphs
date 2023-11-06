from typing import Type
from dataclasses import dataclass
from abc import ABC, abstractmethod

from open_hypergraphs.finite_function import FiniteFunction, IndexedCoproduct
from open_hypergraphs.open_hypergraph import OpenHypergraph
from open_hypergraphs.functor import Functor, FrobeniusFunctor

class Optic(FrobeniusFunctor, ABC):
    # Fwd maps
    F: FrobeniusFunctor

    # Reverse maps
    R: FrobeniusFunctor

    # Compute the object M for each operation x[i] : a[i] → b[i]
    @abstractmethod
    def residual(self, x: FiniteFunction, a: IndexedCoproduct, b: IndexedCoproduct) -> IndexedCoproduct:
        ...

    def map_objects(self, A: FiniteFunction, dtype) -> IndexedCoproduct:
        # Each object A is mapped to F(A) ● R(A)
        FA = self.F.map_objects(A, dtype)
        RA = self.R.map_objects(A, dtype)

        assert len(FA) == len(RA)
        n = len(FA)
        paired = FA + RA
        p = self.FiniteFunction().transpose(2, n, dtype=dtype)

        # TODO: Exposing internals of FiniteFunction here isn't nice.
        sources = self.FiniteFunction()(None, FA.sources.table + RA.sources.table, dtype)
        values = paired.map_indexes(p).values
        return self.IndexedCoproduct()(sources, values)

    def map_operations(self, x: FiniteFunction, A: IndexedCoproduct, B: IndexedCoproduct) -> OpenHypergraph:
        # F(x₀) ● F(x₁) ... F(xn)   :   FA₀ ● FA₁ ... FAn   →   (FB₀ ● M₀) ● (FB₁ ● M₁) ... (FBn ● Mn)
        fwd = self.F.map_operations(x, A, B)

        # R(x₀) ● R(x₁) ... R(xn)   :   (M₀ ● RB₀) ● (M₁ ● RB₁) ... (Mn ● RBn)   →   RA₀ ● RA₁ ... RAn
        rev = self.R.map_operations(x, A, B)

        cls = self.OpenHypergraph()
        dtype = fwd.dtype

        # We'll need these types to build identities and interleavings
        FA = self.F.map_objects(A.values, dtype)
        FB = self.F.map_objects(B.values, dtype)
        RA = self.R.map_objects(A.values, dtype)
        RB = self.R.map_objects(B.values, dtype)
        M  = self.residual(x, A, B)

        # NOTE: we use flatmap here to ensure that each "block" of FB, which
        # might be e.g., F(B₀ ● B₁ ● ... ● Bn) is correctly interleaved:
        # consider that if M = I, then we would need to interleave
        fwd_interleave = self.interleave_blocks(B.flatmap(FB), M, x.to_initial())
        rev_cointerleave = self.interleave_blocks(M, B.flatmap(RB), x.to_initial()).dagger()

        assert fwd.target == fwd_interleave.source
        assert rev_cointerleave.target == rev.source

        i_FB = self.OpenHypergraph().identity(FB.values, x.to_initial(), dtype=dtype)
        i_RB = self.OpenHypergraph().identity(RB.values, x.to_initial(), dtype=dtype)

        # Make this diagram "c":
        #
        #       ┌────┐
        #       │    ├──────────────── FB
        # FA ───┤ Ff │  M
        #       │    ├───┐  ┌────┐
        #       └────┘   └──┤    │
        #                   │ Rf ├──── RA
        # RB ───────────────┤    │
        #                   └────┘
        lhs = (fwd >> fwd_interleave) @ i_RB
        rhs = i_FB @ (rev_cointerleave >> rev)
        c = lhs >> rhs

        # now adapt so that the wires labeled RB and RA are 'bent around'.
        s_i = self.FiniteFunction().inj0(len(FA.values), len(RB.values)) >> c.s
        s_o = self.FiniteFunction().inj1(len(FB.values), len(RA.values)) >> c.t
        s = s_i + s_o

        t_i = self.FiniteFunction().inj0(len(FB.values), len(RA.values)) >> c.t
        t_o = self.FiniteFunction().inj1(len(FA.values), len(RB.values)) >> c.s
        t = t_i + t_o

        d = self.OpenHypergraph()(s, t, c.H)

        # finally interleave the FA with RA and FB with RB
        lhs = self.interleave_blocks(FA, RA, x.to_initial()).dagger()
        rhs = self.interleave_blocks(FB, RB, x.to_initial())
        return lhs >> d >> rhs
    

    def interleave_blocks(self, A: IndexedCoproduct, B: IndexedCoproduct, x: FiniteFunction) -> OpenHypergraph:
        """ An OpenHypergraph whose source is ``A+B`` and whose target is the 'interleaving'
        ``(A₀ + B₀) + (A₁ + B₁) + ... (An + Bn)`` """
        if len(A) != len(B):
            raise ValueError("Can't interleave types of unequal lengths")

        AB = A + B
        dtype = AB.dtype

        s = self.FiniteFunction().identity(len(AB.values), dtype=dtype)
        # NOTE: t is the dagger of transpose(N, 2) because it appears in the target position!
        t = AB.sources.injections(self.FiniteFunction().transpose(2, len(A), dtype=dtype))
        return self.OpenHypergraph().spider(s, t, AB.values, x)
