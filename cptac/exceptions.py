#   Copyright 2018 Samuel Payne sam_payne@byu.edu
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#       http://www.apache.org/licenses/LICENSE-2.0
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

# User-directed exceptions
class CptacError(Exception):
    """Base class for all exceptions we'll raise."""
    pass

class NoInternetError(CptacError):
    """No internet."""
    pass

class InvalidParameterError(CptacError):
    """Invalid parameter."""
    pass

class AmbiguousLatestError(InvalidParameterError):
    """They pass "latest" for a version parameter, but index latest does not match latest version locally installed."""
    pass

class FileError(CptacError):
    """Base class for data-related errors."""
    pass

class DatasetNotInstalledError(FileError):
    """They requested a dataset they haven't installed."""
    pass

class DataVersionNotInstalledError(FileError):
    """They requested a version they haven't installed of a dataset."""
    pass

class MissingFileError(FileError):
    """A data file was missing."""
    pass

class DataError(CptacError):
    """Something was wrong with the data."""
    pass

class ReindexMapError(DataError):
    """Problem reindexing a dataframe."""
    pass

class NoDefinitionsError(DataError):
    """They tried to access definitions for a dataset that doesn't provide any."""
    pass

class DataframeNotIncludedError(DataError):
    """They requested a dataframe that's not included in the dataset."""
    pass

# Warnings
class CptacWarning(UserWarning):
    """Base class for all warnings we'll generate."""
    pass

class FailedReindexWarning(CptacWarning):
    """Error reindexing a dataframe."""
    pass

class ImputedNanWarning(CptacWarning):
    """NaNs were imputed during a dataframe join."""
    pass

class ImputedMutationDataWarning(CptacWarning):
    """Mutation data was imputed during a dataframe join."""
    pass

class ParameterWarning(CptacWarning):
    """We should warn them about a parameter for some reason."""
    pass

class OldDataVersionWarning(CptacWarning):
    """They're using an old data version."""
    pass

class OldPackageVersionWarning(CptacWarning):
    """They're using an old version of the package."""
    pass

class DownloadingNewLatestWarning(CptacWarning):
    """Downloading a new latest data version. If they want to use an old version, they'll have to manually specify it."""
    pass

# Developer-directed exceptions
class CptacDevError(Exception):
    """For exceptions that are probably the developer's fault."""
    pass
