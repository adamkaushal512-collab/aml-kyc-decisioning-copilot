# Policy AML-014: Sanctions Screening Escalation Thresholds

**Scope:** Applies to all customer and counterparty name-screening performed
against sanctions and watchlist data sources during onboarding, periodic
KYC refresh, and transaction monitoring.

## Clauses

1. Every customer, counterparty, and beneficial owner name identified in a
   case must be screened against the applicable sanctions and watchlist
   data source(s) using approved fuzzy name-matching methodology.

2. If a screened name returns a similarity score of **90% or greater**
   against any active sanctions list entry, the case must be automatically
   escalated for mandatory analyst review. Auto-clearance is not permitted
   at or above this threshold under any circumstance.

3. If a screened name returns a similarity score between 75% and 89%
   inclusive, the case is routed to standard analyst review rather than
   automatic escalation; the analyst must document the rationale for
   clearing or escalating within the case record.

4. If a screened name returns a similarity score below 75%, the match is
   treated as a false positive and the case may proceed through normal
   processing without further sanctions-related action, provided no other
   risk factor requires escalation.

5. Escalated cases must not be dispositioned as "cleared" until a second
   reviewer has independently confirmed the match is not a true hit.

6. All screening results, including scores and the disposition rationale,
   must be retained in the case's permanent audit record regardless of
   outcome.
