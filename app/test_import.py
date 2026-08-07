from services.project_importer import ProjectImporter

importer = ProjectImporter(
    r"D:\NikStudio\Episodes\Bath Time Song"
)

importer.import_zip(
    r"D:\NikStudio\Episodes\Bath Time Song\Episode.zip"
)