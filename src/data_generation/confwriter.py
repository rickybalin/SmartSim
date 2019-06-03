
from error.mpo_error import MpoUnsupportedError

class ConfWriter:
    """Reads and writes configuration files of multiple types

       Currently Supported Types
         - namelist(nml)
         - textfile(txt)     ** only append **

      Textfile support is currently specific to MOM6
      Ideally this is the baseclass the model specific
      portions of the data-generation stage of MPO

    """

    def __init__(self):
        self.config = None

    def write_config(self, param_dict, path, filetype):
        if filetype == "txt":
            self.txt(param_dict, path)
        elif filetype == "nml":
            self.nml(param_dict, path)
        else:
            raise MpoUnsupportedError("Data Generation",
                                      "Configuration file type not support yet: "
                                      + filetype)

    def nml(self, param_dict, path):
        """Edit a namelist configuration file"""

        import f90nml
        self.config = f90nml.read(path)
        for k, v in param_dict.items():
            self.deep_update(self.config, k, v)
        self.config.write(path, force=True)


    def txt(self, param_dict, path):
        """Edit a txt based configuration file
           TODO remove MOM6 specific override"""

        with open(path, "a+") as txt_config:
            for k, v in param_dict.items():
                txt_config.write("#override " + k + "=" + str(v) + "\n")


    def deep_update(self, source, key, value):
        """
        Update a nested dictionary or similar mapping.
        Modify ``source`` in place.
        """
        for k, v in source.items():
            if k == key:
                source[k] = value
            elif isinstance(v, dict):
                self.deep_update(source[k], key, value)

        self.config = source

