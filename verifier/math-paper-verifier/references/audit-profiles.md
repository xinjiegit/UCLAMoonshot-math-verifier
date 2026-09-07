# Audit workflow

The public skill has one ordinary manuscript workflow. It does not encode a
benchmark arm, a study protocol, a scoring rule, or a repository-specific
approval process.

## `standard`

Run the independent global and decomposed mathematical passes with web search
disabled. Keep them blind to one another, validate both outputs, and union
findings by location and mathematical failure mechanism. Keep singleton
findings.

Then inventory the paper's load-bearing external obligations with web search
disabled. Resolve that validated inventory in a fresh web-enabled
external-verification pass. The source verifier receives the obligation
artifact rather than the manuscript and may use only independent primary or
official sources. A missing source is unresolved, not evidence that a claim is
false.

Run an independent advisory safeguard review after each completed pass. It
examines recorded conduct and source trust, without feeding information back to
blind workers or changing mathematical findings. Search refinements and apparent
contamination are assessed in context, not by word allowlists. Advisory flags or
an unavailable reviewer are surfaced to the human and never cause automatic
verification retries; integrity failures remain distinct.

Users may request an internal-only audit. In that case stop after the
global/decomposed union and report that external claims were not checked.

## Optional passes

- `argument-spine` traces the dependencies essential to headline claims.
- `refuter` actively searches for a decisive counterexample to central claims.
- `focused-sweep` exhaustively checks a supplied axis such as displayed
  equations, boundary clauses, quantifiers, or a narrower specification.
- `citation-fidelity` verifies cited attributions with web access.

Optional passes run in fresh contexts and retain distinct provenance. An
explicit `only` request suppresses the standard workflow.

## Network boundary

Mathematical passes and the obligation inventory are web-disabled. The
registry-declared source-verification passes are web-enabled automatically for
their own invocation. Retrieved evidence must never be fed back into an
already completed mathematical pass.

The policy is shared across execution modes. CLI launchers configure provider
tools; app-native workers use available per-worker controls and explicit
instructions. Native reports disclose when network restrictions are not
enforced or complete activity exports are unavailable. Separate app contexts
are not a claim of operating-system isolation or removal of inherited settings.
