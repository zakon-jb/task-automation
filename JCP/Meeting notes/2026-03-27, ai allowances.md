Participants: @Dmitry Borin, @Sergey Coox, @Sergey Zhuravlev, @zakon

Hey folks,
Today we discussed how Pre-billing should distinguish between “fake” AI allowances (that will be added to plain IDE licenses like WebStorm, PyCharm, etc.) and real ones coming from license bundles - APP, DotUltimate. Pre-billing should treat the former as just access to AI, while for the latter it should provide AI credits.

The current decision is as follows.
Pre-billing will check both the allowance and its parent license’s product code. If it is one of {APP, DUL}, then it will be processed as a “fair” license with bundled credits. Otherwise, Pre-billing will treat it as just AI access and will not provide any credits.

This technical solution doesn’t look perfect and contradicts the previously taken approach that the quota service doesn’t process product codes in this context.
However, this trade-off is acceptable if there are no plans to extend the list of license bundles in the future.
@mikhail.blagutin, please confirm that there are no such plans.