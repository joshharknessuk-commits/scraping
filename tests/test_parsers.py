from src.detail_parser import parse_additional_html_for_occupancy, parse_detail_html


DETAIL_HTML = """
<html>
  <body>
    <h1 class="heading-large">1 Example Street, London, SE1 0AA</h1>
    <h2>Licence reference SWK-1234567890</h2>
    <div>
      <p>Licence type: <span class="bold">Selective licence</span></p>
      <p>Licence end date: <span class="bold">31/12/2025</span></p>
    </div>
  </body>
</html>
"""


ADDITIONAL_HTML = """
<html>
  <body>
    <div>
      <p>Maximum number of occupants: <span class="bold">5</span></p>
      <p>Occupancy notes: Not specified</p>
    </div>
  </body>
</html>
"""


ADDITIONAL_TEXTUAL_HTML = """
<html>
  <body>
    <p>Maximum permitted occupants - Six persons</p>
  </body>
</html>
"""


def test_parse_detail_html_extracts_fields():
    parsed = parse_detail_html(DETAIL_HTML)

    assert parsed["address"] == "1 Example Street, London, SE1 0AA"
    assert parsed["licence_reference"] == "SWK-1234567890"
    assert parsed["licence_type"] == "Selective licence"
    assert parsed["end_date"] == "31/12/2025"


def test_parse_additional_html_for_occupancy_numeric():
    occupancy = parse_additional_html_for_occupancy(ADDITIONAL_HTML)

    assert occupancy == 5


def test_parse_additional_html_for_occupancy_textual():
    occupancy = parse_additional_html_for_occupancy(ADDITIONAL_TEXTUAL_HTML)

    assert occupancy == "Maximum permitted occupants - Six persons"
