def load_template_and_inject_rows(leads, template_path="dashboard_template.html"):
    with open(template_path, "r", encoding="utf-8") as file:
        html_template = file.read()

    rows_html = ""
    for lead in leads:
        last_active_str = (
            lead["last_active"].strftime("%Y-%m-%d %H:%M:%S")
            if lead.get("last_active") else "-"
        )
        rows_html += f"""
        <tr>
            <td>{lead.get('mobile_number', '-')}</td>
            <td>{lead.get('username') or '-'}</td>
            <td>{lead.get('conversation_summary') or '-'}</td>
            <td>{lead.get('sentiment_label') or '-'}</td>
            <td>{lead.get('sentiment_score') if lead.get('sentiment_score') is not None else '-'}</td>
            <td>{last_active_str}</td>
        </tr>
        """

    final_html = html_template.replace("<!--ROWS_PLACEHOLDER-->", rows_html)
    return final_html