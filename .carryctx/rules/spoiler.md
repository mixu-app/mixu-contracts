# Rule: spoiler safety

- Three progress values stay distinct: `reading_position`, `knowledge_horizon`,
  `graph_view_position`.
- A projection at ordinal `r` exposes nothing with `first_reveal > r` — including
  labels, aliases, relations, identity merges, counts, ordering, layout slots,
  search hits and previews.
- Filtering happens in the query/policy layer, never by hiding rendered views.
- Later evidence appends a transition with its own reveal ordinal; earlier views
  keep the earlier state.
- Any change here needs a `mixu-fixtures` case that fails without the fix.
- A confirmed leak in the evaluated corpus is stop-ship, not a follow-up ticket.
