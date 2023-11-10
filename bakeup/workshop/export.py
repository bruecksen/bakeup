from django.http import HttpResponse
from tablib import Dataset


class DataExport:
    """
    Export data from a ProductionDay
    """

    CSV = "csv"
    JSON = "json"
    LATEX = "latex"
    ODS = "ods"
    TSV = "tsv"
    XLS = "xls"
    XLSX = "xlsx"
    YAML = "yaml"

    FORMATS = {
        CSV: "text/csv; charset=iso-8859-1",
        JSON: "application/json",
        LATEX: "text/plain",
        ODS: "application/vnd.oasis.opendocument.spreadsheet",
        TSV: "text/tsv; charset=utf-8",
        XLS: "application/vnd.ms-excel",
        XLSX: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        YAML: "text/yaml; charset=utf-8",
    }

    def __init__(self, export_format, data, headers, title, dataset_kwargs=None):
        if not self.is_valid_format(export_format):
            raise TypeError(
                'Export format "{}" is not supported.'.format(export_format)
            )

        self.format = export_format
        self.dataset = self.data_to_dataset(data, headers, title, dataset_kwargs)

    @classmethod
    def is_valid_format(self, export_format):
        """
        Returns true if `export_format` is one of the supported export formats
        """
        return export_format is not None and export_format in DataExport.FORMATS.keys()

    def data_to_dataset(self, data, headers, title, dataset_kwargs=None):
        """Transform a table to a tablib dataset."""

        kwargs = {"title": title}
        kwargs.update(dataset_kwargs or {})
        dataset = Dataset(*data, headers=headers, **kwargs)
        return dataset

    def content_type(self):
        """
        Returns the content type for the current export format
        """
        return self.FORMATS[self.format]

    def export(self):
        """
        Returns the string/bytes for the current export format
        """
        return self.dataset.export(self.format)

    def response(self, filename=None):
        """
        Builds and returns a `HttpResponse` containing the exported data

        Arguments:
            filename (str): if not `None`, the filename is attached to the
                `Content-Disposition` header of the response.
        """
        response = HttpResponse(content_type=self.content_type())
        if filename is not None:
            response["Content-Disposition"] = 'attachment; filename="{}"'.format(
                filename
            )

        response.write(self.export())
        return response


class ExportMixin:
    exclude_columns = ()
    dataset_kwargs = None
    export_class = DataExport

    export_format = DataExport.CSV

    def get_export_filename(self, export_format):
        return "{}.{}".format(self.export_name, export_format)

    def get_dataset_kwargs(self):
        return self.dataset_kwargs

    def create_export(self, export_format):
        exporter = self.export_class(
            export_format=export_format,
            data=self.get_data(),
            headers=self.get_headers(),
            title=self.export_name,
            dataset_kwargs=self.get_dataset_kwargs(),
        )

        return exporter.response(filename=self.get_export_filename(export_format))

    def render_to_response(self, context, **kwargs):
        return self.create_export(self.export_format)
