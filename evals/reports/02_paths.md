# Check 2: one recipe per path through the graph

Each recipe was run fresh (its own checkpoint database) against the real MCP nutrition server.

| path | site | terminal | went where expected |
|---|---|---|---|
| A. retry, all matched, summarise | www.savorynothings.com | complete | yes |
| B. retry, hit cap, give up, summarise | www.zenbelly.com | complete_partial | yes |
| C. retry, hit cap, give up, skip card | www.asweetpeachef.com | complete_partial | yes |
| D. retry, give up below cap (no alias), skip card | www.garlicandzest.com | complete_partial | yes |
| E. fetch fails (live blocked, no snapshot) | www.example-recipes.invalid | failed_fetch | yes |

### A. retry, all matched, summarise

- URL: https://www.savorynothings.com/chewy-chocolate-crinkle-cookies/
- Expected because: 'all-purpose flour', 'baking powder', 'white sugar' and 'vanilla' miss on their own wording and each has an alias that hits in round 2; nothing is left unknown; 16 cook comments (>= 5).
- Expected path: `fetch → parse_recipe → parse_ingredients → match_nutrition → match_nutrition → gather_comments → summarise → validate → write`
- Logged path:   `fetch → parse_recipe → parse_ingredients → match_nutrition → match_nutrition → gather_comments → summarise → validate → write`
- Terminal: `complete`: all 9 ingredients matched with grams; card from 15 comments

- Ingredients that drove the path: 2 cups all-purpose flour (all-purpose flour → Wheat flour, white, all-purpose, enriched, bleached: matched); 1.5 teaspoons baking powder (baking powder → Leavening agents, baking powder, double-acting, sodium aluminum sulfate: matched); 1 1/2 cups white sugar (white sugar → granulated sugar: matched); 2 teaspoons vanilla (vanilla → vanilla extract: matched)

### B. retry, hit cap, give up, summarise

- URL: https://www.zenbelly.com/gingerbread/
- Expected because: 'coconut sugar' and 'tapioca starch' each have two aliases that are not in SR28, so they use all 3 attempts and are marked unknown; 19 cook comments.
- Expected path: `fetch → parse_recipe → parse_ingredients → match_nutrition → match_nutrition → match_nutrition → mark_unknown → gather_comments → summarise → validate → write`
- Logged path:   `fetch → parse_recipe → parse_ingredients → match_nutrition → match_nutrition → match_nutrition → mark_unknown → gather_comments → summarise → validate → write`
- Terminal: `complete_partial`: 7 of 15 ingredients without nutrition (4 unknown, 2 hit the 3-attempt cap, 3 no gram weight); card from 17 comments

- Ingredients that drove the path: 3 cups almond flour (almond flour → almond meal → Nuts, almonds, blanched: matched); 1 1/2 cups tapioca starch (plus more for flouring pan) (tapioca starch → tapioca flour → cassava starch: unknown); 1/2 cup coconut flour (coconut flour: unknown); 1 1/2 teaspoons baking soda (baking soda → Leavening agents, baking soda: matched); 2 teaspoons ground ginger (ground ginger → Spices, ginger, ground: matched); 1 teaspoons ground cinnamon (ground cinnamon → Spices, cinnamon, ground: matched); 1/4 teaspoon ground allspice (ground allspice → Spices, allspice, ground: matched); 1/4 teaspoon ground cardamom (ground cardamom → Spices, cardamom: matched); 1/2 teaspoon finely ground sea salt (ground sea salt: unknown); 1 cup coconut sugar (coconut sugar → coconut palm sugar → palm sugar: unknown); 2 teaspoons fresh ginger (ginger → fresh ginger root → Ginger root, raw: matched); 1 cup boiling water (water → Beverages, water, tap, drinking: matched)

### C. retry, hit cap, give up, skip card

- URL: https://www.asweetpeachef.com/healthy-apple-crumble/
- Expected because: 'coconut sugar' exhausts the cap; 'sea salt' has no alias; 4 cook comments (< 5) so no card.
- Expected path: `fetch → parse_recipe → parse_ingredients → match_nutrition → match_nutrition → match_nutrition → mark_unknown → gather_comments → validate → write`
- Logged path:   `fetch → parse_recipe → parse_ingredients → match_nutrition → match_nutrition → match_nutrition → mark_unknown → gather_comments → validate → write`
- Terminal: `complete_partial`: 5 of 12 ingredients without nutrition (4 unknown, 1 hit the 3-attempt cap, 1 no gram weight); no card (4 comments < threshold 5)

- Ingredients that drove the path: 8 cups sliced Granny Smith apples ((approx. 7 apples)) (granny smith apples → Apples, raw, granny smith, with skin: matched); 1/2 cup coconut sugar (plus more to taste if needed) (coconut sugar → coconut palm sugar → palm sugar: unknown); 1/2 fresh lemon zest and juice (plus more to taste if needed) (lemon zest and juice: unknown); 1 tsp ground cinnamon (ground cinnamon → Spices, cinnamon, ground: matched); 1/4 tsp ground nutmeg (ground nutmeg → Spices, nutmeg, ground: matched); 1/8 tsp sea salt (sea salt: unknown); 1 cup almond flour (almond flour → almond meal → Nuts, almonds, blanched: matched); 1/3 cup chopped pecans (can also use walnuts or almonds or a mixture of all 3) (pecans → Nuts, pecans: matched); 1/4 cup pepitas (pepitas → pumpkin seeds → Seeds, pumpkin and squash seed kernels, dried: matched); 1 tsp ground cinnamon (ground cinnamon → Spices, cinnamon, ground: matched); 1/8 tsp sea salt (sea salt: unknown)

### D. retry, give up below cap (no alias), skip card

- URL: https://www.garlicandzest.com/easy-banana-cake-recipe/
- Expected because: 'all purpose flour', 'baking powder', 'cinnamon' and 'greek yogurt' miss in round 1; the first three have an alias that hits in round 2; greek yogurt has none (fat level not stated), so it is given up after 1 attempt without reaching the cap; 1 comment.
- Expected path: `fetch → parse_recipe → parse_ingredients → match_nutrition → match_nutrition → mark_unknown → gather_comments → validate → write`
- Logged path:   `fetch → parse_recipe → parse_ingredients → match_nutrition → match_nutrition → mark_unknown → gather_comments → validate → write`
- Terminal: `complete_partial`: 1 of 11 ingredients without nutrition (1 unknown, 0 hit the 3-attempt cap, 0 no gram weight); no card (1 comments < threshold 5)

- Ingredients that drove the path: 1/2 cup unsalted butter (at room temperature) (unsalted butter → butter without salt: matched); 2 cups all purpose flour (all purpose flour → Wheat flour, white, all-purpose, enriched, bleached: matched); 1 1/2 teaspoons baking powder (baking powder → Leavening agents, baking powder, double-acting, sodium aluminum sulfate: matched); 1/2 teaspoon baking soda (baking soda → Leavening agents, baking soda: matched); 1 teaspoon cinnamon (cinnamon → Spices, cinnamon, ground: matched); 1 cup greek yogurt (greek yogurt: unknown)

### E. fetch fails (live blocked, no snapshot)

- URL: https://www.example-recipes.invalid/no-such-recipe/
- Expected because: host does not resolve and the URL has no pinned snapshot; the run must still end in a declared state.
- Expected path: `fetch → parse_recipe:skipped → parse_ingredients:skipped → match_nutrition:skipped → gather_comments:skipped → validate → write`
- Logged path:   `fetch → parse_recipe:skipped → parse_ingredients:skipped → match_nutrition:skipped → gather_comments:skipped → validate → write`
- Terminal: `failed_fetch`: no snapshot pinned for https://www.example-recipes.invalid/no-such-recipe/

