from abc import ABC, abstractmethod


class BaseBackend(ABC):

    @abstractmethod
    def generate_image(self, scene):
        pass

    @abstractmethod
    def generate_video(self, scene):
        pass