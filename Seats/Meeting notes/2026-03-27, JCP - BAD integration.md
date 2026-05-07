Participants: @zakon, @Denis Linkov, @Sergey Coox, @Michael Blagutin, @Gleb Leonov, @Dmitry Borin, @Iryna Muraveika, @Raman Babich, @Svetlana Shmalko, @Viktor Kiselev

Hey everyone!
Today we discussed migration to Seats and the next steps regarding the JCP-BAD integration topics (e.g. recurrent credit subscriptions).
The migration doc: https://docs.google.com/document/d/1gEQ3fJE3mLQm7lY7yCE2ixoCBuYIsWKbKmuXDNFUFf0/edit?tab=t.0

We covered the migration flow, and it seems that the happy path is fully covered on both ends.
However, we identified some corner cases that should be discussed separately and addressed before the EAP Global launch:
changing customer type: personal → organization
products without a license (e.g. Android Studio)
merging customers after migration

We also highlighted the issue of distinguishing between “fake” and “fair” AI allowances on the pre-billing side. It has already been solved—here is the outcome.

Action points:
(@zakon) Arrange a meeting to discuss recurrent credit subscription (scheduled for next Thursday)
(@zakon & @artem.sarkisov) Update feature priorities for the next milestone (early next week) (see PRD)
(@zakon & @glebleonov) Create a migration checklist as a common ground for all teams