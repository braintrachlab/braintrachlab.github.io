"""Writes content/nomina.txt from Terminologia Neuroanatomica (FIPAT 2017), Chapter 1:
the white matter terms, in TNA order and hierarchy. Run once; afterwards the lab edits content/nomina.txt."""
import os
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# (TNA number, depth, Latin, Latin synonym, UK English, US English (if different), English synonym, other/eponym, endnote)
G = {}
G["General terms"] = [
 (14, 0, "Substantia alba", "", "White matter", "", "White substance", "", ""),
 (15, 0, "Funiculus", "", "Funiculus", "", "", "", ""),
 (16, 0, "Tractus", "", "Tract", "", "", "", ""),
 (17, 1, "Tractus commissuralis", "", "Commissural tract", "", "", "", ""),
 (18, 1, "Tractus proprius", "", "Intrinsic tract", "", "", "", ""),
 (19, 2, "Tractus associationis", "", "Association tract", "", "", "", ""),
 (20, 1, "Tractus longus", "Tractus projectionis", "Long tract", "", "Projection tract", "", ""),
 (21, 2, "Tractus ascendens", "", "Ascending tract", "", "", "", ""),
 (22, 2, "Tractus descendens", "", "Descending tract", "", "", "", ""),
 (23, 0, "Stria", "", "Stria", "", "", "", ""),
 (24, 0, "Fasciculus", "", "Fasciculus", "", "Fascicle", "", ""),
 (25, 0, "Lemniscus", "", "Lemniscus", "", "", "", ""),
 (26, 0, "Decussatio", "", "Decussation", "", "", "", ""),
 (27, 0, "Commissura", "", "Commissure", "", "", "", ""),
 (28, 0, "Neurofibrae centrales", "", "Central nerve fibres", "Central nerve fibers", "", "", ""),
 (31, 1, "Neurofibra associationis", "", "Association nerve fibre", "Association nerve fiber", "", "", ""),
 (32, 1, "Neurofibra commissuralis", "", "Commissural nerve fibre", "Commissural nerve fiber", "", "", ""),
 (33, 1, "Neurofibra projectionis", "", "Projection nerve fibre", "Projection nerve fiber", "", "", ""),
]
G["White matter of the cerebral hemisphere"] = [
 (2417, 0, "Substantia alba hemispherii cerebri", "", "White matter of cerebral hemisphere", "", "White substance of cerebral hemisphere", "", ""),
 (2418, 1, "Centrum semiovale", "", "Semi-oval centre", "Semioval center", "", "",
  "This term, introduced in 1684 by Vieussens as 'Centrum ovale' to indicate the oval shape of the cerebral white matter, continuous with the internal capsule, was later changed into Centrum semiovale by Flatau (1894) and others. In the clinical literature, this term is common usage. It was included by His and colleagues in the BNA."),
 (2419, 1, "Capsula extrema", "", "Extreme capsule", "", "", "", ""),
 (2420, 1, "Capsula externa", "", "External capsule", "", "", "", ""),
 (2421, 1, "Fasciculus peduncularis", "", "Peduncular fasciculus", "", "", "", ""),
 (2422, 1, "Corona radiata", "", "Corona radiata", "", "", "", ""),
]
G["Internal capsule"] = [
 (2423, 0, "Capsula interna", "", "Internal capsule", "", "", "", ""),
 (2424, 1, "Crus anterius", "", "Anterior limb", "", "", "", ""),
 (2425, 2, "Radiatio anterior thalami", "", "Anterior thalamic radiation", "", "", "", ""),
 (2426, 2, "Tractus frontopontinus", "", "Frontopontine tract", "", "", "", ""),
 (2427, 1, "Genu capsulae internae", "", "Genu of internal capsule", "", "", "", ""),
 (2428, 2, "Fibrae corticonucleares", "", "Corticonuclear fibres", "Corticonuclear fibers", "", "", ""),
 (2429, 1, "Crus posterius", "", "Posterior limb", "", "", "", ""),
 (2430, 2, "Radiatio centralis thalami", "", "Central thalamic radiation", "", "", "", ""),
 (2431, 2, "Fibrae corticoreticulares", "", "Corticoreticular fibres", "Corticoreticular fibers", "", "", ""),
 (2432, 2, "Fibrae corticorubrales", "", "Corticorubral fibres", "Corticorubral fibers", "", "", ""),
 (2433, 2, "Fibrae corticospinales", "", "Corticospinal fibres", "Corticospinal fibers", "", "", ""),
 (2434, 2, "Fibrae corticothalamicae", "", "Corticothalamic fibres", "Corticothalamic fibers", "", "", ""),
 (2435, 2, "Fibrae parietopontinae", "", "Parietopontine fibres", "Parietopontine fibers", "", "", ""),
 (2436, 2, "Fibrae thalamoparietales", "", "Thalamoparietal fibres", "Thalamoparietal fibers", "", "", ""),
 (2437, 1, "Pars retrolentiformis", "Crus retrolentiforme", "Retrolentiform limb", "", "Retrolenticular limb", "",
  "The Pars retrolentiformis of the internal capsule should be treated as a separate component, not as part of the posterior limb; Crus retrolentiforme suggested as synonym."),
 (2438, 2, "Fibrae occipitopontinae", "", "Occipitopontine fibres", "Occipitopontine fibers", "", "", ""),
 (2439, 2, "Fibrae occipitotectales", "", "Occipitotectal fibres", "Occipitotectal fibers", "", "", ""),
 (2440, 2, "Radiatio optica", "Fibrae geniculocalcarinae", "Optic radiation", "", "Geniculocalcarine fibres", "Tract of Gratiolet", ""),
 (2441, 2, "Radiatio posterior thalami", "", "Posterior thalamic radiation", "", "", "", ""),
 (2442, 1, "Pars sublentiformis", "Crus sublentiforme", "Sublentiform limb", "", "Sublenticular limb", "",
  "The Pars sublentiformis also forms a separate component of the internal capsule; Crus sublentiforme suggested as synonym."),
 (2443, 2, "Radiatio acustica", "Fibrae geniculotemporales", "Acoustic radiation", "", "Geniculotemporal fibres", "", ""),
 (2444, 2, "Fibrae corticotectales", "", "Corticotectal fibres", "Corticotectal fibers", "", "", ""),
 (2445, 2, "Radiatio optica", "Fibrae geniculocalcarinae", "Optic radiation", "", "Geniculocalcarine fibres", "", ""),
 (2446, 2, "Fibrae temporopontinae", "", "Temporopontine fibres", "Temporopontine fibers", "", "", ""),
 (2447, 2, "Fibrae corticothalamicae", "", "Corticothalamic fibres", "Corticothalamic fibers", "", "", ""),
]
G["Association tracts"] = [
 (2448, 0, "Tractus associationis telencephali", "Tractus associationis cerebri", "Association tracts of telencephalon", "", "Association tracts of cerebrum", "", ""),
 (2449, 1, "Fibrae associationis breves", "Fibrae U-figuratae", "Short association fibres", "Short association fibers", "U-fibres", "Fibrae arcuatae cerebri",
  "The Fibrae U-figuratae (U-shaped fibres) were first described by Meynert (1872), and replaced the term Fibrae arcuatae cerebri (Arnold 1838) that became obsolete."),
 (2450, 1, "Fibrae associationis longae", "", "Long association fibres", "Long association fibers", "", "", ""),
 (2451, 2, "Fasciculus arcuatus", "", "Arcuate fasciculus", "", "", "",
  "The Fasciculus arcuatus (Arcuate fascicle) was long considered to be similar to or part of the Superior longitudinal fascicle. More recent research (Catani, Jones & ffytche 2005, Ann Neurol 57:8-16) identified the Arcuate fascicle as a distinct entity with three components."),
 (2452, 3, "Segmentum anterius", "", "Anterior segment", "", "", "", ""),
 (2453, 3, "Segmentum longum", "", "Long segment", "", "", "", ""),
 (2454, 3, "Segmentum posterius", "", "Posterior segment", "", "", "", ""),
 (2455, 2, "Cingulum", "", "Cingulum", "", "", "", ""),
 (2456, 2, "Capsula extrema", "", "Extreme capsule", "", "", "",
  "The Capsula extrema (Extreme capsule) forms one of the long association systems involved in language processing (see Catani & Thiebaut de Schotten 2012, Atlas of Human Brain Connections, Oxford University Press)."),
 (2457, 2, "Fasciculus longitudinalis inferior", "", "Inferior longitudinal fasciculus", "", "", "", ""),
 (2458, 2, "Fasciculus longitudinalis superior", "", "Superior longitudinal fasciculus", "", "", "",
  "The Fasciculus longitudinalis superior appears to be composed of three bundles (SLF I-III, or superior, middle and inferior; Makris et al. 2005, Cereb Cortex 15:854-869) as in monkeys (Schmahmann & Pandya 2006; Thiebaut de Schotten, Dell'Acqua, Valabregue & Catani 2012, Cortex 48:82-96)."),
 (2459, 2, "Pedunculus temporalis", "", "Temporal peduncle", "", "Temporal stem", "", ""),
 (2460, 3, "Fasciculus uncinatus", "", "Uncinate fasciculus", "", "", "", ""),
 (2461, 3, "Fasciculus occipitofrontalis inferior", "", "Inferior occipitofrontal fasciculus", "", "", "", ""),
 (2462, 2, "Fasciculus occipitofrontalis superior", "", "Superior occipitofrontal fasciculus", "", "", "", ""),
 (2463, 2, "Fasciculus subcallosus", "", "Subcallosal fasciculus", "", "", "Bundle of Muratoff",
  "The Fasciculus subcallosus (Subcallosal fasciculus or Bundle of Muratoff; Muratoff 1893) forms a separate bundle of corticostriatal fibres (see Schmahmann & Pandya 2007, The complex history of the fronto-occipital fasciculus, J Hist Neurosci 16:362-377)."),
 (2464, 2, "Fasciculus frontalis obliquus", "", "Frontal aslant tract", "", "Frontal oblique tract", "",
  "The Fasciculus frontalis obliquus (Frontal aslant tract or Frontal oblique tract) connects the SMA and pre-SMA with the opercular part of the inferior frontal gyrus (Catani, Dell'Acqua, Vergani et al. 2012, Short frontal lobe connections of the human brain, Cortex 48:273-291)."),
 (2465, 2, "Fasciculus frontalis orbitopolaris", "", "Frontal orbitopolar fasciculus", "", "", "", ""),
 (2466, 2, "Fasciculus frontomarginalis", "", "Frontomarginal tract", "", "", "", ""),
 (2467, 2, "Fasciculi occipitales verticales", "", "Vertical occipital fasciculi", "", "", "", ""),
 (2468, 3, "Fibrae laterales", "", "Lateral fibres", "Lateral fibers", "", "", ""),
 (2469, 3, "Fibrae caudales", "", "Caudal fibres", "Caudal fibers", "", "", ""),
 (2470, 2, "Fasciculi occipitales horizontales", "", "Transverse occipital fasciculi", "", "", "", ""),
 (2471, 3, "Fibrae cuneatae", "", "Cuneate fibres", "Cuneate fibers", "", "", ""),
 (2472, 3, "Fibrae linguales", "", "Lingual fibres", "Lingual fibers", "", "", ""),
]
G["Commissural tracts"] = [
 (2473, 0, "Tractus commissurales telencephali", "Tractus commissurales cerebri", "Commissural tracts of telencephalon", "", "Commissural tracts of cerebrum", "", ""),
 (2474, 1, "Corpus callosum", "", "Corpus callosum", "", "", "", "For the gross division of the Corpus callosum (Rostrum, Genu, Truncus, Splenium; TNA 2190-2194), see Morphologia externa."),
 (2475, 2, "Fibrae corporis callosi", "", "Corpus callosum fibres", "Corpus callosum fibers", "", "", ""),
 (2476, 2, "Radiatio corporis callosi", "", "Radiation of corpus callosum", "", "", "", ""),
 (2477, 3, "Forceps minor", "Forceps frontalis", "Forceps minor", "", "Frontal forceps", "", ""),
 (2478, 3, "Forceps major", "Forceps occipitalis", "Forceps major", "", "Occipital forceps", "", ""),
 (2479, 3, "Tapetum", "", "Tapetum", "", "", "", ""),
 (2480, 1, "Commissura hippocampi", "Psalterium", "Hippocampal commissure", "", "Psalterium", "Commissura fornicis",
  "The old term Psalterium has been added, much in use by clinicians (see Amaral, Insausti & Cowan 1984, J Comp Neurol 224:307-336)."),
 (2481, 1, "Commissura anterior", "", "Anterior commissure", "", "", "", ""),
 (2482, 2, "Pars anterior", "", "Anterior part", "", "", "", ""),
 (2483, 2, "Pars posterior", "", "Posterior part", "", "", "", ""),
]
G["Long tracts (projection)"] = [
 (2484, 0, "Tractus longi telencephali", "Tractus longi cerebri", "Long tracts of telencephalon", "", "", "", ""),
 (2485, 1, "Tractus descendentes", "", "Descending tracts", "", "", "", ""),
 (2486, 2, "Fibrae corticostriatales", "", "Corticostriatal fibres", "Corticostriatal fibers", "", "", ""),
 (2487, 2, "Fibrae corticothalamicae", "", "Corticothalamic fibres", "Corticothalamic fibers", "", "", ""),
 (2488, 2, "Fibrae corticotectales", "", "Corticotectal fibres", "Corticotectal fibers", "", "", ""),
 (2489, 2, "Tractus pyramidalis", "", "Pyramidal tract", "", "", "", ""),
 (2490, 3, "Fibrae corticorubrales", "", "Corticorubral fibres", "Corticorubral fibers", "", "", ""),
 (2491, 3, "Fibrae corticoreticulares", "", "Corticoreticular fibres", "Corticoreticular fibers", "", "", ""),
 (2492, 3, "Fibrae corticonucleares", "", "Corticonuclear fibres", "Corticonuclear fibers", "", "", ""),
 (2493, 3, "Fibrae corticospinales", "", "Corticospinal fibres", "Corticospinal fibers", "", "", ""),
 (2494, 2, "Fibrae corticopontinae", "", "Corticopontine fibres", "Corticopontine fibers", "", "", ""),
 (2495, 3, "Tractus frontopontinus", "", "Frontopontine tract", "", "", "", ""),
 (2496, 3, "Fibrae parietopontinae", "", "Parietopontine fibres", "Parietopontine fibers", "", "", ""),
 (2497, 3, "Fibrae temporopontinae", "", "Temporopontine fibres", "Temporopontine fibers", "", "", ""),
 (2498, 3, "Fibrae occipitopontinae", "", "Occipitopontine fibres", "Occipitopontine fibers", "", "", ""),
]
G["Fornix and hippocampal white matter"] = [
 (2361, 0, "Alveus hippocampi", "", "Alveus", "", "", "", ""),
 (2362, 0, "Fimbria hippocampi", "", "Fimbria", "", "", "", ""),
 (2363, 0, "Fornix", "", "Fornix", "", "", "", ""),
 (2364, 1, "Crus fornicis", "", "Crus of fornix", "", "", "", ""),
 (2365, 1, "Commissura hippocampi", "Psalterium", "Hippocampal commissure", "", "Psalterium", "Commissura fornicis",
  "The old term Psalterium has been added, much in use by clinicians."),
 (2366, 1, "Corpus fornicis", "", "Body of fornix", "", "", "", ""),
 (2367, 1, "Columna fornicis", "", "Column of fornix", "", "", "", ""),
 (2368, 2, "Fibrae precommissurales", "", "Precommissural fornix", "", "", "", ""),
 (2369, 2, "Fibrae postcommissurales", "", "Postcommissural fornix", "", "", "", ""),
]

HEAD = open(os.path.join(ROOT, "content", "news.txt")).read().split("# ======================================================================")[1]
out = ["# ======================================================================" + HEAD + "# ======================================================================\n",
"""#
#  NOMINA ANATOMICA — the white matter in Terminologia Neuroanatomica (TNA), FIPAT 2017, Chapter 1.
#  Source: FIPAT. Terminologia Neuroanatomica. FIPAT.library.dal.ca. Federative International Programme
#  for Anatomical Terminology, February 2017 (CC BY-ND 4.0; the terms are in the public domain).
#
#  One entry per term, in TNA order. Fields:
#  tna:        TNA number
#  group:      section of the page (entries with the same group are shown together)
#  level:      0, 1, 2, 3 = position in the TNA hierarchy (indentation)
#  latin:      official Latin term                                   (required)
#  latin_syn:  Latin synonym
#  english:    UK English term
#  us:         US English term, when different
#  synonyms:   English synonyms
#  other:      eponyms and older terms
#  note:       TNA endnote
# ======================================================================
"""]
for g, rows in G.items():
    for (n, d, la, ls, uk, us, es, ot, note) in rows:
        e = [f"tna: {n}", f"group: {g}", f"level: {d}", f"latin: {la}"]
        if ls: e.append(f"latin_syn: {ls}")
        e.append(f"english: {uk}")
        if us: e.append(f"us: {us}")
        if es: e.append(f"synonyms: {es}")
        if ot: e.append(f"other: {ot}")
        if note: e.append(f"note: {note}")
        out.append("\n".join(e) + "\n")
open(os.path.join(ROOT, "content", "nomina.txt"), "w").write("\n".join(out))
print(sum(len(r) for r in G.values()), "terms")
