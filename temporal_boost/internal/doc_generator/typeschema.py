from pydantic import BaseModel


class TypeSchema(BaseModel):
    name: str
    fields: dict | None = None

    def __hash__(self) -> str:
        return hash(self.name)

    def nav(self) -> str:
        return f"""
            <li>
                <a href="#schema_{self.name}"><span class="badge bg-danger">Schema</span> {self.name}</a>
            </li>
        """

    def html(self) -> str:
        fields: str = f"""<div>Schema {self.name}:</div><table class="table">
            <thead>
                <tr>
                <th scope="col">#</th>
                <th scope="col">First</th>
                <th scope="col">Last</th>
                <th scope="col">Handle</th>
                </tr>
            </thead>
            <tbody>"""
        for field in self.fields:
            print(dir(self.fields.get(field).type))
            fields = fields + f"""<tr>
            <th scope="row">{self.fields.get(field).name}</th>
            <td>{str(self.fields.get(field).type)}</td>
            <td>Otto</td>
            <td>@mdo</td>
            </tr>"""
        fields = fields + "</tbody></table>"
        return fields
