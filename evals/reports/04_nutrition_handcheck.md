# Check 4: nutrition hand-check against food ids

For each ingredient with nutrition, the raw SR28 `ABBREV.txt` line for its food id was read directly (not through the agent's database module), the gram weight re-derived from the basis the record cites, and the nutrient contribution recomputed as value_per_100g × grams / 100.

## Southern Fudge Pie (rcp_8f14802a32)

Partial: 1 of 8 ingredients have no nutrition (0 unmatched food, 1 matched but no gram weight); totals cover the other 7 only.

| ingredient | food id | SR28 short description | grams (hand) | kcal/100 g | kcal hand / record | result |
|---|---|---|---|---|---|---|
| 3/4 cup salted butter | 01001 | BUTTER,WITH SALT | 170.4 | 717 | 1221.8 / 1221.8 | match |
| 3 (1 ounce) unsweetened chocolate squares | 19078 | Baking chocolate, unsweetened, squares | 85.0 | 642 | 546.0 / 546.0 | match |
| 3 large eggs | 01123 | EGG,WHL,RAW,FRSH | 150.0 | 143 | 214.5 / 214.5 | match |
| 1 1/2 cups sugar | 19335 | SUGARS,GRANULATED | 302.4 | 387 | 1170.3 / 1170.3 | match |
| 3/4 cup all-purpose flour | 20081 | WHEAT FLR,WHITE,ALL-PURPOSE,ENR,BLEACHED | 93.8 | 364 | 341.2 / 341.2 | match |
| 1 teaspoon vanilla extract | 02050 | VANILLA EXTRACT | 4.2 | 288 | 12.1 / 12.1 | match |
| 1/2 cup chopped pecans ((or walnuts)) | 12142 | PECANS | 54.5 | 691 | 376.6 / 376.6 | match |
| vanilla ice cream, chocolate syrup and chopped pecans | 19095 | - | - | - | - | no_gram_weight |

Recipe total energy: record 3882.5 kcal, hand sum 3882.5 kcal.

## Banana Cream Pie Recipe (rcp_b3d4fd62b7)

Partial: 3 of 16 ingredients have no nutrition (0 unmatched food, 3 matched but no gram weight); totals cover the other 13 only.

| ingredient | food id | SR28 short description | grams (hand) | kcal/100 g | kcal hand / record | result |
|---|---|---|---|---|---|---|
| 1 1/2 cups graham cracker crumbs (reserve 1 1/2 tablespoons) | 18173 | - | - | - | - | no_gram_weight |
| 6 tablespoons butter melted | 01001 | BUTTER,WITH SALT | 85.2 | 717 | 610.9 / 610.9 | match |
| 1/3 cup sugar | 19335 | SUGARS,GRANULATED | 67.2 | 387 | 260.0 / 260.0 | match |
| 2 bananas sliced | 09040 | - | - | - | - | no_gram_weight |
| 1 1/4 cups 2% milk | 01079 | MILK,RED FAT,FLUID,2% MILKFAT,W/ ADDED VIT A & VITAMIN D | 305.0 | 50 | 152.5 / 152.5 | match |
| 1 cup whipping cream | 01052 | CREAM,FLUID,LT WHIPPING | 239.0 | 292 | 697.9 / 697.9 | match |
| 2/3 cup sugar | 19335 | SUGARS,GRANULATED | 134.4 | 387 | 520.2 / 520.2 | match |
| 1/8 teaspoon salt | 02047 | SALT,TABLE | 0.8 | 0 | 0.0 / 0.0 | match |
| 1/4 cup cornstarch | 20027 | CORNSTARCH | 32.0 | 381 | 121.9 / 121.9 | match |
| 4 large egg yolks (room temperature) | 01125 | EGG,YOLK,RAW,FRSH | 68.0 | 322 | 219.0 / 219.0 | match |
| 1 teaspoon vanilla extract | 02050 | VANILLA EXTRACT | 4.2 | 288 | 12.1 / 12.1 | match |
| 2 tablespoons unsalted butter | 01145 | BUTTER,WITHOUT SALT | 28.4 | 717 | 203.6 / 203.6 | match |
| 1 cup whipping cream | 01052 | CREAM,FLUID,LT WHIPPING | 239.0 | 292 | 697.9 / 697.9 | match |
| 1 1/2 tablespoons powdered sugar | 19336 | SUGARS,POWDERED | 11.2 | 389 | 43.8 / 43.8 | match |
| 1/2 teaspoon vanilla extract | 02050 | VANILLA EXTRACT | 2.1 | 288 | 6.0 / 6.0 | match |
| bananas for garnish | 09040 | - | - | - | - | no_gram_weight |

Recipe total energy: record 3545.8 kcal, hand sum 3545.8 kcal.

## Paleo Gingerbread (rcp_d534b880e0)

Partial: 7 of 15 ingredients have no nutrition (4 unmatched food, 3 matched but no gram weight); totals cover the other 8 only.

| ingredient | food id | SR28 short description | grams (hand) | kcal/100 g | kcal hand / record | result |
|---|---|---|---|---|---|---|
| butter (ghee, or shortening for greasing the pan) | 01001 | - | - | - | - | no_gram_weight |
| 3 cups almond flour | 12062 | - | - | - | - | no_gram_weight |
| 1 1/2 cups tapioca starch (plus more for flouring pan) | - | - | - | - | - | no_food_id |
| 1/2 cup coconut flour | - | - | - | - | - | no_food_id |
| 1 1/2 teaspoons baking soda | 18372 | LEAVENING AGENTS,BAKING SODA | 6.9 | 0 | 0.0 / 0.0 | match |
| 2 teaspoons ground ginger | 02021 | GINGER,GROUND | 3.6 | 335 | 12.1 / 12.1 | match |
| 1 teaspoons ground cinnamon | 02010 | CINNAMON,GROUND | 2.6 | 247 | 6.4 / 6.4 | match |
| 1/4 teaspoon ground allspice | 02001 | ALLSPICE,GROUND | 0.5 | 263 | 1.2 / 1.2 | match |
| 1/4 teaspoon ground cardamom | 02006 | SPICES,CARDAMOM | 0.5 | 311 | 1.6 / 1.6 | match |
| 1/2 teaspoon finely ground sea salt | - | - | - | - | - | no_food_id |
| 1 cup coconut sugar | - | - | - | - | - | no_food_id |
| 1 cup molasses (use true molasses if you can find it) | 19304 | MOLASSES | 337.0 | 290 | 977.3 / 977.3 | match |
| 2 teaspoons fresh ginger | 11216 | GINGER ROOT,RAW | 4.0 | 80 | 3.2 / 3.2 | match |
| 1 cup boiling water | 14411 | BEVERAGES,H2O,TAP,DRINKING | 236.8 | 0 | 0.0 / 0.0 | match |
| 4 eggs | 01123 | - | - | - | - | no_gram_weight |

Recipe total energy: record 1001.8 kcal, hand sum 1001.8 kcal.

Largest absolute difference across grams and nutrients: 0.0092 (rounding only).

