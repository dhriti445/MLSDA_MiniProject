"""Writes a SMALL SEED corpus so the system runs offline. Texts are paraphrased from memory and some policy
values are placeholders: REPLACE with the official CBIC/DGFT PDFs in corpus/ (ingest handles .pdf) and verify."""
H73 = {
 "7308": "Structures (excluding prefabricated buildings of heading 9406) and parts of structures (for example, bridges, towers, lattice masts, doors, windows, shutters, balustrades, pillars and columns), of iron or steel; plates, rods, angles, shapes, sections, tubes and the like, prepared for use in structures, of iron or steel.",
 "7310": "Tanks, casks, drums, cans, boxes and similar containers, for any material (other than compressed or liquefied gas), of iron or steel, of a capacity not exceeding 300 litres, whether or not lined or heat-insulated, but not fitted with mechanical or thermal equipment.",
 "7312": "Stranded wire, ropes, cables, plaited bands, slings and the like, of iron or steel, not electrically insulated.",
 "7315": "Chain and parts thereof, of iron or steel.",
 "7317": "Nails, tacks, drawing pins, corrugated nails, staples (other than those of heading 8305) and similar articles, of iron or steel, whether or not with heads of other material, but excluding such articles with heads of copper.",
 "7318": "Screws, bolts, nuts, coach screws, screw hooks, rivets, cotters, cotter pins, washers (including spring washers) and similar articles, of iron or steel.",
 "7319": "Sewing needles, knitting needles, bodkins, crochet hooks, embroidery stilettos and similar articles, for use in the hand, of iron or steel; safety pins and other pins of iron or steel, not elsewhere specified or included.",
 "7320": "Springs and leaves for springs, of iron or steel.",
 "7321": "Stoves, ranges, grates, cookers (including those with subsidiary boilers for central heating), barbecues, braziers, gas rings, plate warmers and similar non-electric domestic appliances, and parts thereof, of iron or steel.",
 "7323": "Table, kitchen or other household articles and parts thereof, of iron or steel; iron or steel wool; pot scourers and scouring or polishing pads, gloves and the like, of iron or steel.",
 "7324": "Sanitary ware and parts thereof, of iron or steel (for example, bath tubs, sinks and washbasins).",
 "7326": "Other articles of iron or steel.",
}
H96 = {
 "9603": "Brooms, brushes (including brushes constituting parts of machines, appliances or vehicles), hand-operated mechanical floor sweepers, not motorised, mops and feather dusters; prepared knots and tufts for broom or brush making; paint pads and rollers; squeegees (other than roller squeegees).",
 "9604": "Hand sieves and hand riddles.",
 "9605": "Travel sets for personal toilet, sewing or shoe or clothes cleaning.",
 "9606": "Buttons, press-fasteners, snap-fasteners and press-studs, button moulds and other parts of these articles; button blanks.",
 "9607": "Slide fasteners and parts thereof.",
 "9608": "Ball point pens; felt tipped and other porous-tipped pens and markers; fountain pens, stylograph pens and other pens; duplicating stylos; propelling or sliding pencils; pen-holders, pencil-holders and similar holders; parts (including caps and clips) of the foregoing articles, other than those of heading 9609.",
 "9609": "Pencils (other than pencils of heading 9608), crayons, pencil leads, pastels, drawing charcoals, writing or drawing chalks and tailors' chalks.",
 "9613": "Cigarette lighters and other lighters, whether or not mechanical or electrical, and parts thereof other than flints and wicks.",
 "9614": "Smoking pipes (including pipe bowls) and cigar or cigarette holders, and parts thereof.",
 "9615": "Combs, hair-slides and the like; hairpins, curling pins, curling grips, hair-curlers and the like, other than those of heading 8516, and parts thereof.",
 "9616": "Scent sprays and similar toilet sprays, and mounts and heads therefor; powder-puffs and pads for the application of cosmetics or toilet preparations.",
 "9617": "Vacuum flasks and other vacuum vessels, complete with cases; parts thereof other than glass inners.",
 "9618": "Tailors' dummies and other lay figures; automata and other animated displays used for shop window dressing.",
 "9619": "Sanitary towels (pads) and tampons, napkins and napkin liners for babies and similar articles, of any material.",
 "9620": "Monopods, bipods, tripods and similar articles.",
}
out = ["# SEED CORPUS - paraphrased placeholders. Replace/extend with official CBIC and DGFT documents; verify every text and policy value.\n"]
def blk(i, t, ch, text, src): out.append(f"@@ id={i} type={t} chapter={ch} source={src}\n{text}\n")
blk("GRI_1", "gri", "0", "GRI 1: The titles of Sections, Chapters and sub-Chapters are provided for ease of reference only. For legal purposes, classification shall be determined according to the terms of the headings and any relative Section or Chapter Notes and, provided such headings or Notes do not otherwise require, according to the following provisions.", "seed-GRI")
blk("GRI_2", "gri", "0", "GRI 2: (a) Any reference to an article includes that article incomplete or unfinished, provided it has the essential character of the complete article. (b) Any reference to a material or substance includes mixtures or combinations of that material with other materials; classification of goods consisting of more than one material shall be according to the principles of GRI 3.", "seed-GRI")
blk("GRI_3a", "gri", "0", "GRI 3(a): When goods are prima facie classifiable under two or more headings, the heading which provides the most specific description shall be preferred to headings providing a more general description.", "seed-GRI")
blk("GRI_3b", "gri", "0", "GRI 3(b): Composite goods made up of different materials or components which cannot be classified by reference to GRI 3(a) shall be classified as if they consisted of the material or component which gives them their essential character.", "seed-GRI")
blk("GRI_3c", "gri", "0", "GRI 3(c): When goods cannot be classified by reference to GRI 3(a) or 3(b), they shall be classified under the heading which occurs last in numerical order among those which equally merit consideration.", "seed-GRI")
blk("GRI_4", "gri", "0", "GRI 4: Goods which cannot be classified in accordance with the above rules shall be classified under the heading appropriate to the goods to which they are most akin.", "seed-GRI")
blk("GRI_6", "gri", "0", "GRI 6: For legal purposes, the classification of goods in the subheadings of a heading shall be determined according to the terms of those subheadings and any related Subheading Notes.", "seed-GRI")
blk("NOTE_S15_1", "note", "73", "Section XV Note 1: This Section does not cover articles of Chapter 96 (for example, brushes, buttons, slide fasteners, sanitary towels and napkins for babies). It also does not cover articles of Chapter 82 or 83 where those chapters specifically name them.", "seed-SXV")
blk("NOTE_C73_1", "note", "73", "Chapter 73 Note 1: In this Chapter the expression cast iron applies to products obtained by casting; the expression iron or steel includes alloy steel and stainless steel.", "seed-C73")
blk("NOTE_C73_2", "note", "73", "Chapter 73 Note 2: Heading 7326 covers only articles of iron or steel that are not included in the preceding headings of this Chapter or in other Chapters of the Nomenclature.", "seed-C73")
blk("NOTE_C96_1", "note", "96", "Chapter 96 Note 1: This Chapter does not cover articles of heading 6601, 6602 or 6603 (umbrellas, walking-sticks, whips) or articles of Chapter 71 where precious metal is the essential material.", "seed-C96")
for k, v in H73.items(): blk(f"H{k}", "heading", "73", f"{k} - {v}", "seed-C73")
for k, v in H96.items(): blk(f"H{k}", "heading", "96", f"{k} - {v}", "seed-C96")
for k in list(H73) + list(H96):
    blk(f"POL_{k}", "policy", k[:2], f"Export policy for {k}: Free. [UNVERIFIED PLACEHOLDER - confirm against the DGFT ITC(HS) export schedule before relying on it]", "seed-DGFT")
open("corpus/seed/seed_corpus.txt", "w").write("\n".join(out))
print("blocks", sum(1 for l in out for x in l.splitlines() if x.startswith("@@")))
