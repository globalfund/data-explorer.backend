import logging
import os

from dotenv import load_dotenv
from flask import Flask, abort, request
from rb_core_backend.data_management import RBCoreDataManagement
from rb_core_backend.mongo import RBCoreBackendMongo
from rb_core_backend.preprocess_dataset import PreprocessDataOptions, RBCoreDatasetPreprocessor
from rb_core_backend.util import configure_logger, json_return

from api.tgf_dataset_manager import TGFDatasetManager


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
    mongo_username=os.getenv("MONGO_USERNAME"),
    mongo_password=os.getenv("MONGO_PASSWORD"),
    mongo_auth_source=os.getenv("MONGO_AUTH_SOURCE"),
    database_name="the-data-explorer-db",
    fs_db_name="FederatedSearchIndex",
)
# - Create a TGFDatasetManager instance
gf_dataset_manager = TGFDatasetManager(
    mongo_client=mongo_client,
    data_preprocessor=dataset_preprocessor,
    logger=logger,
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


if __name__ == "__main__":
    print("Run with `uv run flask app:app` or `gunicorn app:app`")
