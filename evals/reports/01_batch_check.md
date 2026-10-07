# Check 1: batch termination, required fields, match rate

Runs checked: 25 of 25. Problems: 0.
Retry cap: 3. Highest attempt count on any ingredient: 3.

**Match rate: 263/309 = 85.1%** of ingredient lines matched to a USDA SR28 food id. 241 of them also have a gram weight, so nutrition covers 78.0% of lines. 46 unknown; 22 matched but without a gram weight.

| recipe id | title | terminal state | matched | ingredients | max attempts | cook notes | check |
|---|---|---|---|---|---|---|---|
| rcp_8f14802a32 | Southern Fudge Pie | complete_partial | 8 | 8 | 2 | produced | ok |
| rcp_88989bf2ca | Peach Cobbler with Almond Topping | complete_partial | 14 | 15 | 2 | produced | ok |
| rcp_954df896bf | Easy Black Forest Cake Recipe | complete | 17 | 17 | 2 | produced | ok |
| rcp_6cc580a3f9 | Banana Cream Pie | complete_partial | 7 | 7 | 2 | produced | ok |
| rcp_456ba2c583 | Cake Batter Chocolate Chip Cookies | complete_partial | 8 | 11 | 3 | produced | ok |
| rcp_37c8a93478 | Old Fashioned Butter Rolls | complete_partial | 8 | 9 | 2 | produced | ok |
| rcp_d534b880e0 | Paleo Gingerbread | complete_partial | 11 | 15 | 3 | produced | ok |
| rcp_40775bc489 | Low-Carb Pumpkin Bars With Cream Cheese Frosting | complete_partial | 10 | 14 | 3 | produced | ok |
| rcp_7c62b972de | Coconut Cake Recipe | complete_partial | 10 | 13 | 3 | produced | ok |
| rcp_d79db9d191 | The Best Vegan Chocolate Cake | complete_partial | 16 | 17 | 2 | produced | ok |
| rcp_888a61d803 | Pecan Pie Cookies | complete_partial | 17 | 17 | 2 | produced | ok |
| rcp_b503aae880 | Oreo Cheesecake Bites Recipe (+Video) | complete_partial | 6 | 6 | 3 | produced | ok |
| rcp_0d13d9e9fb | Apple Cider Donuts | complete_partial | 13 | 17 | 2 | produced | ok |
| rcp_aa1633c698 | Perfect Sugar Cookie Recipe | complete_partial | 10 | 11 | 3 | produced | ok |
| rcp_fc65dea92d | The Best Chocolate Cake Recipe {Ever} | complete_partial | 8 | 13 | 3 | produced | ok |
| rcp_b3d4fd62b7 | Banana Cream Pie Recipe | complete_partial | 16 | 16 | 2 | produced | ok |
| rcp_3af5e08cb9 | Chewy Chocolate Crinkle Cookies | complete | 9 | 9 | 2 | produced | ok |
| rcp_4af70562af | Vegan Carrot Cake | complete_partial | 16 | 20 | 3 | skipped_below_threshold | ok |
| rcp_d2ebfad24c | Pineapple Pound Cake | complete_partial | 10 | 11 | 2 | skipped_below_threshold | ok |
| rcp_0f42aaa00b | Peanut Butter Blossoms (No Eggs) | complete_partial | 9 | 10 | 3 | skipped_below_threshold | ok |
| rcp_199960060f | Healthy Apple Crumble | complete_partial | 8 | 12 | 3 | skipped_below_threshold | ok |
| rcp_2a33fb3cde | Easy Banana Cake Recipe | complete_partial | 10 | 11 | 2 | skipped_below_threshold | ok |
| rcp_33acda5403 | Blueberry Cobbler | complete_partial | 7 | 8 | 2 | skipped_below_threshold | ok |
| rcp_499b68545e | Peanut Butter Pie | complete_partial | 6 | 10 | 3 | skipped_below_threshold | ok |
| rcp_d098681b06 | Best Ever Pumpkin Pie Recipe | complete_partial | 9 | 12 | 2 | skipped_below_threshold | ok |

## Every unmatched ingredient, with the queries tried

| recipe id | ingredient line | attempts | queries tried | reason |
|---|---|---|---|---|
| rcp_88989bf2ca | Zest from 1 large lemon | 1 | zest from 1 lemon | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_456ba2c583 | 1 1/4 cup (190g) yellow or vanilla boxed cake mix (not the whole box and you just need the DRY mix) | 1 | vanilla boxed cake mix | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_456ba2c583 | 1 cup (180g) chocolate chips (I use 1/2 cup white and 1/2 cup semi-sweet) | 1 | chocolate chips | no other names to try after 1 attempt(s); last: rejected: best hit 'Cookies, chocolate chip, dry mix' is not a close match (cost 4.3 > 1.0) |
| rcp_456ba2c583 | 1/2 cup (80g) sprinkles | 3 | sprinkles → nonpareils → candy sprinkles | no acceptable match within the 3-attempt cap; last: no_candidates |
| rcp_37c8a93478 | 2 cups milk | 1 | milk | no other names to try after 1 attempt(s); last: rejected: best hit 'Milk, sheep, fluid' is not a close match (cost 1.3 > 1.0) |
| rcp_d534b880e0 | 1 1/2 cups tapioca starch (plus more for flouring pan) | 3 | tapioca starch → tapioca flour → cassava starch | no acceptable match within the 3-attempt cap; last: no_candidates |
| rcp_d534b880e0 | 1/2 cup coconut flour | 1 | coconut flour | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_d534b880e0 | 1/2 teaspoon finely ground sea salt | 1 | ground sea salt | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_d534b880e0 | 1 cup coconut sugar | 3 | coconut sugar → coconut palm sugar → palm sugar | no acceptable match within the 3-attempt cap; last: no_candidates |
| rcp_40775bc489 | 1/4 cup Coconut Flour | 1 | coconut flour | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_40775bc489 | 1/2 tsp Pink Salt | 2 | pink salt → himalayan salt | no other names to try after 2 attempt(s); last: no_candidates |
| rcp_40775bc489 | 3/4 cup Brown Sugar Alternative Sweetener | 1 | brown sugar alternative sweetener | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_40775bc489 | 1/2 cup Powdered Sweetener Blend | 1 | powdered sweetener blend | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_7c62b972de | 1/2 cup oil | 1 | oil | no other names to try after 1 attempt(s); last: rejected: ambiguous between 'Oil, oat' and 'Oil, palm' |
| rcp_7c62b972de | 1 cup shredded coconut | 1 | shredded coconut | no other names to try after 1 attempt(s); last: rejected: best hit 'Nuts, coconut meat, dried (desiccated), sweetened, shredded' is not a close match (cost 6.3 > 1.0) |
| rcp_7c62b972de | 1 teaspoon coconut extract (or vanilla extract) | 1 | coconut extract | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_d79db9d191 | 1 1/2 cups vegan butter, softened (baking sticks preferred) | 1 | vegan butter | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_0d13d9e9fb | 3 cups apple cider ((see note 2)) | 2 | apple cider → sweet apple cider | no other names to try after 2 attempt(s); last: no_candidates |
| rcp_0d13d9e9fb | 1 teaspoon apple pie spice ((see note 3)) | 1 | apple pie spice | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_0d13d9e9fb | 1/2 cup milk | 1 | milk | no other names to try after 1 attempt(s); last: rejected: best hit 'Milk, sheep, fluid' is not a close match (cost 1.3 > 1.0) |
| rcp_0d13d9e9fb | 3/4 teaspoon apple pie spice | 1 | apple pie spice | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_aa1633c698 | Sprinkles, sugars and nonpareils | 3 | sprinkles → nonpareils → candy sprinkles | no acceptable match within the 3-attempt cap; last: no_candidates |
| rcp_fc65dea92d | 1 teaspoon kosher salt | 2 | kosher salt → coarse salt | no other names to try after 2 attempt(s); last: no_candidates |
| rcp_fc65dea92d | 1 teaspoon espresso powder (homemade or store-bought) | 3 | espresso powder → instant espresso powder → instant espresso | no acceptable match within the 3-attempt cap; last: no_candidates |
| rcp_fc65dea92d | 1 cup milk (or buttermilk, almond, or coconut milk) | 1 | milk | no other names to try after 1 attempt(s); last: rejected: best hit 'Milk, sheep, fluid' is not a close match (cost 1.3 > 1.0) |
| rcp_fc65dea92d | 1/2 cup vegetable oil (or canola oil, or melted coconut oil) | 1 | vegetable oil | no other names to try after 1 attempt(s); last: rejected: best hit 'Vegetable oil, palm kernel' is not a close match (cost 2.0 > 1.0) |
| rcp_fc65dea92d | Chocolate Buttercream Frosting Recipe | 1 | chocolate buttercream frosting recipe | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_4af70562af | 3/4 cup dairy-free milk (we use almond milk) | 1 | dairy-free milk | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_4af70562af | 2 ounces vegan butter (diced and softened at room temperature) | 1 | vegan butter | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_4af70562af | 1/2 lemon (the grated zest) | 1 | lemon | no other names to try after 1 attempt(s); last: rejected: best hit 'Lemons, raw, without peel' is not a close match (cost 2.3 > 1.0) |
| rcp_4af70562af | 4 ounces vegan cream cheese | 1 | vegan cream cheese | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_d2ebfad24c | 1 cup crushed pineapple (drained (save juice for glaze)) | 1 | pineapple | no other names to try after 1 attempt(s); last: rejected: best hit 'Pineapple, raw, all varieties' is not a close match (cost 2.3 > 1.0) |
| rcp_0f42aaa00b | 48 Hershey’s Kisses, unwrapped | 3 | hershey’s kisses → chocolate kisses → milk chocolate kisses | no acceptable match within the 3-attempt cap; last: no_candidates |
| rcp_199960060f | 1/2 cup coconut sugar (plus more to taste if needed) | 3 | coconut sugar → coconut palm sugar → palm sugar | no acceptable match within the 3-attempt cap; last: no_candidates |
| rcp_199960060f | 1/2 fresh lemon zest and juice (plus more to taste if needed) | 1 | lemon zest and juice | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_199960060f | 1/8 tsp sea salt | 1 | sea salt | no other names to try after 1 attempt(s); last: rejected: best hit 'KASHI, TLC, Pita Crisps, Sea Salt' is not a close match (cost 9.0 > 1.0) |
| rcp_199960060f | 1/8 tsp sea salt | 1 | sea salt | no other names to try after 1 attempt(s); last: rejected: best hit 'KASHI, TLC, Pita Crisps, Sea Salt' is not a close match (cost 9.0 > 1.0) |
| rcp_2a33fb3cde | 1 cup greek yogurt | 1 | greek yogurt | no other names to try after 1 attempt(s); last: rejected: best hit 'Yogurt, Greek, plain, nonfat' is not a close match (cost 1.3 > 1.0) |
| rcp_33acda5403 | 3/4 tsp kosher salt | 2 | kosher salt → coarse salt | no other names to try after 2 attempt(s); last: no_candidates |
| rcp_499b68545e | 1/8 teaspoon fine sea salt | 1 | sea salt | no other names to try after 1 attempt(s); last: rejected: best hit 'KASHI, TLC, Pita Crisps, Sea Salt' is not a close match (cost 9.0 > 1.0) |
| rcp_499b68545e | 1 cup natural peanut butter (be sure that it’s very well stirred) | 1 | natural peanut butter | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_499b68545e | 1/4 teaspoon fine sea salt | 1 | sea salt | no other names to try after 1 attempt(s); last: rejected: best hit 'KASHI, TLC, Pita Crisps, Sea Salt' is not a close match (cost 9.0 > 1.0) |
| rcp_499b68545e | whipped cream (chocolate shavings, crumbled Oreos, chopped Reese’s, etc) | 1 | whipped cream | no other names to try after 1 attempt(s); last: rejected: best hit 'Cream, whipped, cream topping, pressurized' is not a close match (cost 2.0 > 1.0) |
| rcp_d098681b06 | 1 recipe all-butter pie crust ((or store bought single layer pie crust)) | 1 | all-butter pie crust | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_d098681b06 | 1 teaspoon vanilla bean paste | 1 | vanilla bean paste | no other names to try after 1 attempt(s); last: no_candidates |
| rcp_d098681b06 | 1/2 teaspoon kosher salt | 2 | kosher salt → coarse salt | no other names to try after 2 attempt(s); last: no_candidates |

## Matched to a food id but no gram weight (nutrition left out, not estimated)

| recipe id | ingredient line | food id | why no grams |
|---|---|---|---|
| rcp_8f14802a32 | vanilla ice cream, chocolate syrup and chopped pecans | 19095 | no single quantity in recipe line |
| rcp_88989bf2ca | 2 tablespoons plain whole-milk Greek yogurt | 01293 | food has no USDA volume portion usable for 'tbsp' |
| rcp_88989bf2ca | Vanilla ice cream or whipped cream, for serving | 19095 | no single quantity in recipe line |
| rcp_6cc580a3f9 | bananas (4-5 small bananas, or 2-3 large ones) | 09040 | no single quantity in recipe line |
| rcp_456ba2c583 | 1 egg, at room temperature | 01123 | count without size or weight; no USDA portion to convert it |
| rcp_d534b880e0 | butter (ghee, or shortening for greasing the pan) | 01001 | no single quantity in recipe line |
| rcp_d534b880e0 | 3 cups almond flour | 12062 | matched food is a stand-in for nutrients only; its USDA portion weights do not apply |
| rcp_d534b880e0 | 4 eggs | 01123 | count without size or weight; no USDA portion to convert it |
| rcp_40775bc489 | 1 cup Almond Flour | 12062 | matched food is a stand-in for nutrients only; its USDA portion weights do not apply |
| rcp_d79db9d191 | 4-5 cups powdered sugar | 19336 | no single quantity in recipe line |
| rcp_d79db9d191 | 1/4-1/2 cup unsweetened almond milk | 14091 | no single quantity in recipe line |
| rcp_888a61d803 | 1 heaping cup chopped toasted pecans | 12142 | measure is marked heaping/scant, so the volume is not exact |
| rcp_b503aae880 | 2 eggs | 01123 | count without size or weight; no USDA portion to convert it |
| rcp_0d13d9e9fb | 1 egg | 01123 | count without size or weight; no USDA portion to convert it |
| rcp_aa1633c698 | 1 egg | 01123 | count without size or weight; no USDA portion to convert it |
| rcp_b3d4fd62b7 | 1 1/2 cups graham cracker crumbs (reserve 1 1/2 tablespoons) | 18173 | matched food is a stand-in for nutrients only; its USDA portion weights do not apply |
| rcp_b3d4fd62b7 | 2 bananas sliced | 09040 | count without size or weight; no USDA portion to convert it |
| rcp_b3d4fd62b7 | bananas for garnish | 09040 | no single quantity in recipe line |
| rcp_4af70562af | 1 inch ginger (grated) | 11216 | unit 'inch' has no exact gram conversion |
| rcp_199960060f | 1 cup almond flour | 12062 | matched food is a stand-in for nutrients only; its USDA portion weights do not apply |
| rcp_d098681b06 | 2 eggs, (room temperature) | 01123 | count without size or weight; no USDA portion to convert it |
| rcp_d098681b06 | 2 egg yolks, (room temperature) | 01125 | count without size or weight; no USDA portion to convert it |
