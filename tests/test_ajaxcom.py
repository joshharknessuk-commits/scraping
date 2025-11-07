from src.ajaxcom import extract_main_html


def test_extract_main_html_concatenates_main_content():
    ops = [
        {
            "operation": "container",
            "options": {
                "method": "html",
                "target": "#main-content",
                "value": "<div>First</div>",
            },
        },
        {
            "operation": "container",
            "options": {
                "method": "html",
                "target": "#main-content",
                "value": "<p>Second</p>",
            },
        },
        {
            "operation": "container",
            "options": {
                "method": "html",
                "target": "#other",
                "value": "<span>Ignore</span>",
            },
        },
    ]

    html = extract_main_html(ops)

    assert html == "<div>First</div><p>Second</p>"
