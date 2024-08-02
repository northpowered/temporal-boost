import types
from dataclasses import _MISSING_TYPE

from pydantic import BaseModel


class TypeSchema(BaseModel):
    name: str
    fields: dict | None = None

    def __hash__(self) -> int:
        return hash(self.name)

    def nav(self) -> str:
        return f"""
            <li>
                <a class="schemas-nav-element" href="#schema_{self.name}"><span class="badge bg-danger">  </span> {self.name}</a>
            </li>
        """

    def html(self) -> str:
        fields: str = f"""
        <div id="schema_{self.name}">
            <h4><span class="badge bg-danger">Schema</span> Schema {self.name}:</h4>
        </div>
        <table class="table table-temporal-style">
            <thead>
                <tr>
                <th scope="col">Field name</th>
                <th scope="col">Field type</th>
                <th scope="col">Default value</th>
                </tr>
            </thead>
        <tbody>
        """
        for field in self.fields:
            # Field type check
            field_type: str = ""
            if isinstance(self.fields.get(field).type, type):
                field_type = str(self.fields.get(field).type.__name__)

            if isinstance(self.fields.get(field).type, types.UnionType):
                field_type = self.fields.get(field).type
            # Default value check
            field_default: str = ""
            field_default = self.fields.get(field).default
            if isinstance(self.fields.get(field).default, _MISSING_TYPE):
                field_default = " - "
            fields = (
                fields
                + f"""<tr>
            <th scope="row">{self.fields.get(field).name}</th>
            <td>{field_type}</td>
            <td>{field_default}</td>
            </tr>"""
            )
        fields = fields + "</tbody></table>"
        return fields
