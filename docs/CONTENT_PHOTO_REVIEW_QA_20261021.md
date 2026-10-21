# Publication photo review and direct links

A selected publication photo was restricted to a small cropped preview. The shared editor now offers a labelled button that opens a large contained image. Closing it restores keyboard focus and retains unsaved publication text. The preview is scoped to the business, publication and asset.

A post URL containing `plan_id` and `item_id` now opens the requested visible post without requiring the special `story_facts` focus parameter. The publication textarea has an explicit accessible name. Russian channel-count labels use a grammatical static label.

Validation: two editor regression tests passed, including large-image open/close, focus return and retained unsaved text. The production-based adjacent editor and partnership suite passed 37 tests; frontend build passed. Existing content plans were not regenerated and posts were not approved or published.

The mobile partnership list also requests an explicit `view=mobile` response that omits unused raw search/enrichment payloads. The default web response is unchanged. A live request for the same business decreased from 16,322,376 to 3,105,763 response bytes; this is a payload reduction, not a claim about phone loading time.
