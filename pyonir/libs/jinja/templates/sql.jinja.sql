CREATE TABLE {{data.table}} (
    {% for col in data.all_fields %}
    {{col}} {{data.file_data.get(col).upper()}} {{"NOT NULL" if col in data.required_fields}}{{"," if not loop.last else ""}}
    {% endfor %}

    {% for fk in data.foreign_keys %}
    FOREIGN KEY ({{fk}}) REFERENCES {{data.table}}.{{fk}} (fk)
    {% endfor %}
);