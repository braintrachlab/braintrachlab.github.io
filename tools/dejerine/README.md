Regenerates the animated Dejerine plate (assets/img/dejerine-lines.svg and dejerine-1895.png):

    python3 tools/dejerine/streamlines.py tools/dejerine/source-plate.png assets/img/dejerine-lines.svg assets/img/dejerine-1895.png

The direction of every streamline is read from Gillet's own hatching (structure tensor of the
engraving). Where the hatching is unreadable, the direction of the white-matter band is used.
Strokes stop as soon as they would bend more than ~9° per step or ~55° in total, so no fibre
loops or jumps into another bundle. dejerine.py provides the section mask and removes the
label leader lines.
