Regenerates the animated arcuate fasciculus on the Research page (assets/img/arcuate.svg, arcuate-tint.png):

    python3 tools/arcuate/arcuate.py tools/arcuate/source.png assets/img

Stroke directions are read from the rendered fibres of source.png (long segment red, anterior green,
posterior yellow); strokes stop before bending more than ~7° per step or ~50° in total.
The drawing unfurls along the tract, from the temporal terminations to the frontal lobe.
After regenerating any figure, run tools/build_site.py so the version stamps are updated.
