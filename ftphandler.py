import mimetypes
from pyftpdlib.handlers import FTPHandler
from django.contrib.auth.models import User
from filer.models.foldermodels import Folder
from filer.models.imagemodels import Image
from filer_app.models import FilerVideo, FilerSubtitles


class FileHandler(FTPHandler):
    def on_file_received(self, file):
        file_location = file.split("\\")
        file_name = file_location[-1]
        location =  f"{file_location[-3]}/{file_location[-2]}/{file_name}"
        mime_type_as_tuple = mimetypes.guess_type(file_name)
        mime_type = mime_type_as_tuple[0] 
        file_type = mime_type.split("/")[-2]
        owner = User.objects.filter(username=self.get_repr_info().__getitem__("user"))[0]
        file_size = self.get_repr_info().__getitem__("bytes-trans")

        if file_type == "video":
            FilerClass = FilerVideo
            folder = Folder.objects.filter(name="videos")[0]
        elif file_type == "image":
            FilerClass = Image
            folder = Folder.objects.filter(name="images")[0]
        elif file_type == "text":
            FilerClass = FilerSubtitles
            folder = Folder.objects.filter(name="subtitles")[0]

        new_filer_object = FilerClass(
            file=location
            ,_file_size=file_size,
            original_filename=file_name,
            folder=folder,
            owner=owner,
            mime_type=mime_type
            )
        new_filer_object.generate_sha1()
        new_filer_object.save()
