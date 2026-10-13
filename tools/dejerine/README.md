Regenerates the animated Dejerine plate (assets/img/dejerine-lines.svg and dejerine-1895.png):

    python3 tools/dejerine/dejerine2.py tools/dejerine/source-plate.png assets/img/dejerine-lines.svg assets/img/dejerine-1895.png

dejerine2.py follows the medial axis of the white matter (from the centrum semiovale into
each gyrus, down the internal capsule and into the temporal lobe); dejerine.py only provides
the section mask and the removal of the label leader lines.
