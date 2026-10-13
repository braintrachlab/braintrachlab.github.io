Regenerates the animated Dejerine plate (assets/img/dejerine-lines.svg and dejerine-1895.png):

    python3 tools/dejerine/dejerine_systems.py tools/dejerine/plate-hires.png tools/dejerine/guides.png assets/img
    python3 tools/build_site.py      # updates the version stamps

- plate-hires.png: the original engraving (high resolution)
- guides.png: the same plate with guide lines — red commissural, green association, blue projection
  (built from the latest annotated copy with:
   python3 tools/dejerine/register_guides.py tools/dejerine/plate-hires.png tools/dejerine/guides-v3-annotated.png tools/dejerine/guides.png)
- green-areas.txt: points of the areas to colour as association where no line is drawn

The direction of every streamline is read from Gillet's hatching; the guides only decide the
colour (fibre system) of each streamline. Fibres far from any guide stay neutral slate.

Animation: commissural fibres grow left to right, projection fibres top to bottom, association fibres outwards.

Local corrections: guides-v4-region.png replaces the guides only inside the rectangle in region-v4.txt
(guides.png = guides-v3.png outside it). Inside that rectangle the projection fibres also follow the blue
guides continuously, so they do not stop where the engraving's hatching breaks off.
