import logging
import os
import re

from dotenv import load_dotenv
from flask import Flask, abort, request
from rb_core_backend.data_management import RBCoreDataManagement
from rb_core_backend.external_sources.index import RBCoreExternalSources
from rb_core_backend.external_sources.kaggle import RBCoreExternalSourceKaggle
from rb_core_backend.external_sources.who import RBCoreExternalSourceWHO
from rb_core_backend.mongo import RBCoreBackendMongo
from rb_core_backend.preprocess_dataset import PreprocessDataOptions, RBCoreDatasetPreprocessor
from rb_core_backend.util import configure_logger, json_return

from api.tgf_dataset_manager import TGFDatasetManager

KAGGLE_SOURCE = "Kaggle"
WHO_SOURCE = "WHO"
# Indexing all 500 pages of Kaggle datasets takes hours, KAGGLE_INDEX_MAX_PAGES limits it to the most voted ones.
KAGGLE_MAX_PAGES = 500
DATASET_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
# The file types that can be uploaded, limited to the ones the installed parsers can read.
UPLOAD_FILE_EXTENSIONS = (".csv", ".tsv", ".json", ".xlsx", ".xlsm", ".parquet")
UPLOAD_CHUNK_SIZE = 1024 * 1024
MAX_SEARCH_LIMIT = 100


# Create a subclass implementing RBCoreDatasetPreprocessor
class TGFRBCoreDatasetPreprocessor(RBCoreDatasetPreprocessor):
    def preprocess_data(
        self,
        name: str,
        create_ds: bool = False,
        table: str = None,
        db: dict = None,
        api: dict = None,
        options: PreprocessDataOptions = PreprocessDataOptions(),
    ) -> str:
        # Custom preprocessing steps can be added here
        return super().preprocess_data(name, create_ds, table, db, api, options)


# Load all app requirements
# - Load the environment variables
load_dotenv()
# - Setup and confirm the logger
configure_logger()
logger = logging.getLogger(__name__)
# - Create a RBCoreDataManagement instance
data_manager = RBCoreDataManagement(
    location=os.getenv("DATA_EXPLORER_LOCATION", "/app/")
)
# - Create a RBCorePreprocessDataset instance
# -- Instantiate the subclass
dataset_preprocessor = TGFRBCoreDatasetPreprocessor(
    data_manager=data_manager, logger=logger
)
# - Create a RBCoreBackendMongo instance
mongo_client = RBCoreBackendMongo(
    mongo_host=os.getenv("MONGO_HOST"),
    mongo_username=os.getenv("MONGO_INITDB_ROOT_USERNAME")
    or os.getenv("MONGO_USERNAME"),
    mongo_password=os.getenv("MONGO_INITDB_ROOT_PASSWORD")
    or os.getenv("MONGO_PASSWORD"),
    mongo_auth_source=os.getenv("MONGO_AUTH_SOURCE", "admin"),
    database_name=os.getenv("MONGO_INITDB_DATABASE", "the-data-explorer-db"),
    fs_db_name="FederatedSearchIndex",
)
# - Create a TGFDatasetManager instance
gf_dataset_manager = TGFDatasetManager(
    mongo_client=mongo_client,
    data_preprocessor=dataset_preprocessor,
    logger=logger,
)
# - Create the external sources
# -- rb-core stages files relative to the working directory.
os.makedirs("./staging", exist_ok=True)
try:
    kaggle_index_max_pages = int(os.getenv("KAGGLE_INDEX_MAX_PAGES") or KAGGLE_MAX_PAGES)
except ValueError:
    kaggle_index_max_pages = KAGGLE_MAX_PAGES
kaggle_source = RBCoreExternalSourceKaggle(
    mongo_client=mongo_client,
    dataset_preprocessor=dataset_preprocessor,
    index_max_pages=kaggle_index_max_pages,
)
who_source = RBCoreExternalSourceWHO(
    mongo_client=mongo_client, dataset_preprocessor=dataset_preprocessor
)
external_sources = RBCoreExternalSources(
    mongo_client=mongo_client,
    all_sources={
        KAGGLE_SOURCE: {
            "index": kaggle_source.index,
            "download": kaggle_source.download,
        },
        WHO_SOURCE: {"index": who_source.index, "download": who_source.download},
    },
)
# - Set up the flask app
# -- Set up auth key for requests
authorized_keys = [os.getenv("GF_BACKEND_API_KEY", "ZIMMERMAN")]
# -- Instantiate the app
app = Flask(__name__)


# -- Add a before_request function to check API key
@app.before_request
def check_api_key():
    api_key = request.headers.get("Authorization")
    if api_key not in authorized_keys:
        abort(401)  # Unauthorized


# General Routes
@app.route("/health-check", methods=["GET"])
def health_check():
    return json_return(200, "OK")


# The Global Fund Dataset Routes
@app.route("/update-tgf-datasets", methods=["GET"])
def update_tgf_datasets():
    message, code = gf_dataset_manager.download_datasets()
    return json_return(code, message)


@app.route("/force-update-tgf-dataset/<dataset_name>", methods=["GET"])
def force_update_tgf_dataset(dataset_name: str):
    message, code = gf_dataset_manager.force_update_dataset(dataset_name)
    return json_return(code, message)


# Data access routes
@app.route("/dataset/<string:ds_name>", methods=["GET"])
def get_dataset(ds_name: str) -> dict:
    """Request to get a dataset. Paginated through request args page and page_size.

    Args:
        ds_name (str): Dataset name

    Returns:
        dict: code and dataset or error message
    """
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 10))

    logging.debug(f"route: /dataset/<string:ds_name> - Getting dataset {ds_name}")
    try:
        res = data_manager.load_parsed_data(ds_name, page, page_size)
    except Exception as e:
        logging.error(f"Error in route: /dataset/<string:ds_name> - {str(e)}")
        res = "Sorry, something went wrong in our dataset retrieval. Contact the admin for more information."
    code = 200 if not isinstance(res, str) else 500
    return json_return(code, res)


@app.route("/sample-data/<string:ds_name>", methods=["GET"])
def sample_data(ds_name: str) -> dict:
    """Get the sample dataset for a given dataset name.

    Args:
        ds_name (str): Dataset name

    Returns:
        dict: code and sample dataset or error message
    """
    logging.debug(f"route: /sample-data/<string:ds_name> - Sampling dataset {ds_name}")
    try:
        res = data_manager.load_sample_data(ds_name)
    except Exception as e:
        logging.error(f"Error in route: /sample-data/<string:ds_name> - {str(e)}")
        res = "Sorry, something went wrong in our dataset sampling. Contact the admin for more information."
    code = 200 if not isinstance(res, str) else 500
    return json_return(code, res)


# External source routes
@app.route("/external-sources/index", methods=["GET"])
def external_sources_index():
    """(Re)index all external sources. Indexing Kaggle can take a long time."""
    return json_return(200, external_sources.external_search_index())


@app.route("/external-sources/force-reindex/<string:source>", methods=["GET"])
def external_sources_force_reindex(source: str):
    """(Re)index a single external source, for example WHO or Kaggle."""
    if source not in external_sources.all_sources:
        return json_return(
            404,
            f"Unknown source, expected one of: {', '.join(external_sources.all_sources)}",
        )
    return json_return(200, external_sources.external_search_force_reindex(source))


@app.route("/external-sources/counts", methods=["GET"])
def external_sources_counts():
    """Get the number of available datasets (files) per external source."""
    counts = external_sources.count_external_sources()
    if isinstance(counts, str):
        return json_return(500, counts)
    return json_return(200, counts)


@app.route("/external-sources/search", methods=["GET"])
def external_sources_search():
    """Search the indexed external sources. Paginated through request args limit and offset.

    Request args:
        q (str): The search term, leave empty to list everything.
        source (str): The source to search in, can be provided multiple times. Defaults to all sources.
        limit (int): The maximum number of datasets to return.
        offset (int): The number of datasets to skip.
        sort_by (str): name, updatedDate or createdDate. Defaults to relevance, or name without a search term.

    Returns:
        dict: code and a list of datasets, one for every file of every matching dataset.
    """
    query = request.args.get("q", "").strip()
    sources = [
        source
        for source in request.args.getlist("source")
        if source in external_sources.all_sources
    ]
    try:
        limit = min(max(int(request.args.get("limit", 20)), 1), MAX_SEARCH_LIMIT)
        offset = max(int(request.args.get("offset", 0)), 0)
    except ValueError:
        return json_return(400, "limit and offset have to be numbers.")

    res = external_sources.search_external_sources(
        query,
        sources,
        legacy=True,
        limit=limit,
        offset=offset,
        sort_by=request.args.get("sort_by"),
    )
    if isinstance(res, str):
        return json_return(500, res)
    return json_return(200, res)


@app.route("/external-sources/download", methods=["POST"])
def external_sources_download():
    """Download a dataset from an external source, and make it available as the dataset with the provided id.

    Expects a search result from /external-sources/search as JSON body, extended with an `id`.
    """
    external_dataset = request.get_json(silent=True) or {}
    ds_id = external_dataset.get("id")
    if not isinstance(ds_id, str) or not DATASET_ID_PATTERN.match(ds_id):
        return json_return(400, "A valid dataset id is required.")
    if (
        external_dataset.get("source") not in external_sources.all_sources
        or not isinstance(external_dataset.get("url"), str)
        or not isinstance(external_dataset.get("name"), str)
    ):
        return json_return(400, "The provided external dataset is not valid.")

    # The sources validate the url and name themselves, and report what went wrong.
    res = external_sources.download_external_source(external_dataset)
    if res != "Success":
        return json_return(500, res)
    return json_return(200, "Success")


# File upload routes
@app.route("/upload-file/<string:ds_id>", methods=["POST"])
def upload_file(ds_id: str):
    """Upload a data file, and make it available as the dataset with the provided id.

    Expects the raw file as request body, and the original file name as request arg `filename`.
    """
    if not DATASET_ID_PATTERN.match(ds_id):
        return json_return(400, "A valid dataset id is required.")
    extension = os.path.splitext(request.args.get("filename", ""))[1].lower()
    if extension not in UPLOAD_FILE_EXTENSIONS:
        return json_return(
            400,
            f"Unsupported file type, please upload one of: {', '.join(UPLOAD_FILE_EXTENSIONS)}",
        )

    ds_name = f"{ds_id}{extension}"
    staging_path = f"./staging/{ds_name}"
    try:
        with open(staging_path, "wb") as f:
            while chunk := request.stream.read(UPLOAD_CHUNK_SIZE):
                f.write(chunk)
        # A preprocessor holds the dataframe it is working on, so uploads each get their own.
        preprocessor = TGFRBCoreDatasetPreprocessor(
            data_manager=data_manager, logger=logger
        )
        res = preprocessor.preprocess_data(ds_name, create_ds=True)
    except Exception as e:
        logging.error(f"Error in route: /upload-file/<string:ds_id> - {str(e)}")
        res = "Sorry, something went wrong while processing your file. Contact the admin for more information."
    finally:
        if os.path.exists(staging_path):
            os.remove(staging_path)
    if res != "Success":
        # The file readers report unreadable files with a bare "error".
        if not isinstance(res, str) or " " not in res:
            res = "Sorry, we were unable to read your file. Please check that it contains a table of data."
        return json_return(422, res)
    sample = data_manager.load_sample_data(ds_id)
    if isinstance(sample, str) or not sample.get("count"):
        data_manager.remove_parsed_files(ds_id)
        return json_return(422, "Sorry, we could not find any rows of data in your file.")
    return json_return(200, "Success")


@app.route("/dataset/<string:ds_name>", methods=["DELETE"])
def delete_dataset(ds_name: str):
    """Remove the parsed files of an uploaded or externally sourced dataset."""
    if not DATASET_ID_PATTERN.match(ds_name) or ds_name.startswith("gf_"):
        return json_return(400, "A valid dataset id is required.")
    res = data_manager.remove_parsed_files(ds_name)
    return json_return(200 if res == "Success" else 500, res)


if __name__ == "__main__":
    print("Run with `uv run flask app:app` or `gunicorn app:app`")
