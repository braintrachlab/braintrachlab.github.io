Regenerates the three FAT plates on the Research page (assets/img/fat-*.svg / *.png):

    python3 tools/fat/fat.py tools/fat/source-figure.png assets/img

Streamline directions are read from the rendered fibres of the original figure
(Citro et al., Nature Communications 2026); strokes stop before bending more than
~7° per step or ~45° in total, so no pathway is invented.
