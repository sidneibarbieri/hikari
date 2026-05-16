"""Admin upload endpoint that imports a Hikari backup ZIP."""

import os

from flask import redirect, render_template, url_for
from werkzeug.utils import secure_filename

from CTFd.utils.decorators import admins_only

from .. import hikari_importer
from ..hikari_forms import ImportHikariCTFdForm


def register(blueprint) -> None:
    """Attach /admin/import-hikari-ctf to the plugin blueprint."""

    @blueprint.route("/admin/import-hikari-ctf", methods=["GET", "POST"])
    @admins_only
    def hikari_import_ctf():
        form = ImportHikariCTFdForm()
        if form.validate_on_submit():
            file = form.file_import.data
            if file:
                filename = secure_filename(file.filename)
                upload_path = os.path.join("/tmp", filename)
                file.save(upload_path)
                importer = hikari_importer.HikariImporter(upload_path)
                importer.import_all()
            return redirect(url_for("hikariplugin.hikari_main"))

        return render_template("hikari-import.html", form=form)
