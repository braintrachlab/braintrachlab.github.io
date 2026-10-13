Regenerates the three FAT plates on the Research page (assets/img/fat-*):

    python3 tools/fat/fat2.py tools/fat/source-figure.png tools/fat/source-clean.png assets/img

- source-figure.png: the published figure with the fascicles (Citro et al., Nature Communications 2026)
- source-clean.png: the same brains without fascicles, with the species silhouettes

Streamlines are traced on source-figure.png (directions read from the rendered fibres; strokes
stop before bending more than ~7° per step or ~45° in total) and registered onto the clean
brains: the lateral view and the medial inset are registered separately.
