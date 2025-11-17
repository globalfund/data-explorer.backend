import hashlib
import json
import logging
import os
from datetime import datetime

import numpy as np
import pandas as pd
import requests
from rb_core_backend.mongo import RBCoreBackendMongo
from rb_core_backend.preprocess_dataset import RBCoreDatasetPreprocessor

GF_DATA_URLS = {
    "gf_results.csv": "https://data-service.theglobalfund.org/file_download/gf_reported_results_dataset/CSV",
    "gf_pledges_contributions.csv": "https://data-service.theglobalfund.org/file_download/pledges_contributions_reference_rate_dataset/CSV",  # NOQA: E501
    "gf_eligibility.csv": "https://data-service.theglobalfund.org/file_download/eligibility_dataset/CSV",
    "gf_allocations.csv": "https://data-service.theglobalfund.org/file_download/allocations_dataset/CSV",
    "gf_grant_implementation.csv": "https://data-service.theglobalfund.org/file_download/grant_implementation_periods/CSV",  # NOQA: E501
    "gf_grant_commitments.csv": "https://data-service.theglobalfund.org/file_download/grant_commitments_reference_rate_dataset/CSV",  # NOQA: E501
    "gf_grant_disbursements.csv": "https://data-service.theglobalfund.org/file_download/grant_disbursements_reference_rate_dataset/CSV",  # NOQA: E501
    "gf_grant_budgets.csv": "https://data-service.theglobalfund.org/file_download/grant_budgets_reference_rate/CSV",
    "gf_grant_expenditures_modules_interventions.csv": "https://data-service.theglobalfund.org/file_download/grant_expendituress_modules_interventions_reference_rate_dataset/CSV",  # NOQA: E501
    "gf_grant_expenditures_investment_landscape.csv": "https://data-service.theglobalfund.org/file_download/grant_expendituress_investment_landscape_reference_rate_dataset/CSV",  # NOQA: E501
    "gf_grant_targets_results.csv": "https://data-service.theglobalfund.org/file_download/grant_targets_results_dataset/CSV",  # NOQA: E501
}  # Note: This could be loaded from a config file in the future, depending on stakeholder desires.


class TGFDatasetManager:
    """Manages The Global Fund datasets."""

    def __init__(
        self,
        mongo_client: RBCoreBackendMongo,
        data_preprocessor: RBCoreDatasetPreprocessor,
        logger: logging.Logger,
    ):
        """Initializes the TGFDatasetManager.

        Args:
            mongo_client (RBCoreBackendMongo): A connector to MongoDB, to store and retrieve dataset information.
            data_preprocessor (RBCoreDatasetPreprocessor): An instance responsible for preprocessing datasets.
            logger (logging.Logger): Logger for logging messages.
        """
        self.mongo_client = mongo_client  # To be used to retrieve MongoDB IDs when connected to GF Stack
        self.data_preprocessor = data_preprocessor
        self.logger = logger

    def download_datasets(self) -> tuple[str, int]:
        """Function to download The Global Fund datasets,
        trigger preprocessing if they are updated, finally updates metadata.

        Returns:
            tuple[str, int]: A message and HTTP status code indicating success or failure.
        """
        message = "Success"
        code = 200

        try:
            metadata, now_datetime = self._load_metadata()

            self.logger.info("download_datasets:: Downloading datasets...")
            for key, value in GF_DATA_URLS.items():
                preprocess_message = self._preprocess_gf_dataset(
                    value, metadata, key, now_datetime
                )
                if preprocess_message != "Success":
                    self.logger.warning(
                        f"download_datasets:: Preprocessing message for {key}: {preprocess_message}"
                    )
                    return preprocess_message, 500
            with open("./staging/metadata.json", "w") as file:
                json.dump(metadata, file, default=self._json_safe, indent=4)
            self.logger.info("download_datasets:: Updated metadata.json for ")
        except Exception as e:
            message = "Failed to download datasets."
            self.logger.error(f"download_datasets:: {message}. Error:\n{e}")
            code = 500
        return message, code

    def force_update_dataset(self, dataset_name: str) -> tuple[str, int]:
        """Force updates and preprocesses a specific The Global Fund dataset.

        Args:
            dataset_name (str): The name of the dataset to force update.

        Returns:
            tuple[str, int]: A message and HTTP status code indicating success or failure.
        """
        message = "Success"
        code = 200

        try:
            metadata, now_datetime = self._load_metadata()
            dataset_name = f"{dataset_name}.csv"
            if dataset_name not in GF_DATA_URLS:
                return f"Dataset {dataset_name} not found in our Global Fund datasets!"

            self.logger.info(
                f"force_update_dataset:: Forcing update for dataset: {dataset_name}"
            )
            preprocess_message = self._preprocess_gf_dataset(
                GF_DATA_URLS[dataset_name],
                metadata,
                dataset_name,
                now_datetime,
                force=True,
            )
            if preprocess_message != "Success":
                self.logger.warning(
                    f"force_update_dataset:: Preprocessing message for {dataset_name}: {preprocess_message}"
                )
                return preprocess_message, 500

            with open("./staging/metadata.json", "w") as file:
                json.dump(metadata, file, default=self._json_safe, indent=4)
            self.logger.info("force_update_dataset:: Updated metadata.json")
        except Exception as e:
            message = "Failed to force update dataset."
            self.logger.error(f"force_update_dataset:: {message}. Error:\n{e}")
            code = 500
        return message, code

    def _load_metadata(self) -> tuple[dict, datetime]:
        """Loads the metadata from the metadata.json file.

        Returns:
            tuple[dict, datetime]: The metadata dictionary and the current datetime.
        """
        try:
            now_datetime = datetime.now().isoformat()
            metadata = json.load(open("./staging/metadata.json"))
            self.logger.info("_load_metadata:: Loaded existing metadata.json")
        except Exception as e:
            metadata = {}
            self.logger.info(
                f"_load_metadata:: Could not load existing metadata.json: {e}, creating new..."
            )
        metadata["DateTimeUpdated"] = now_datetime
        return metadata, now_datetime

    def _preprocess_gf_dataset(
        self,
        value: str,
        metadata: dict,
        key: str,
        now_datetime: datetime,
        force: bool = False,
    ) -> str:
        """Downloads and preprocesses a The Global Fund dataset if updated.
        Args:
            value (str): The URL of the dataset to download.
            metadata (dict): The metadata dictionary to update.
            key (str): The filename to save the dataset as.
            now_datetime (datetime): The current datetime for metadata update.
            force (bool): Whether to force preprocessing regardless of hash comparison.

        Returns:
            str: A message indicating success or failure of preprocessing.
        """
        # Download file from `value` url and save it as `key`
        response = requests.get(value)
        old_hash = metadata.get(key, {}).get("hash", "")
        new_hash = hashlib.md5(response.content).hexdigest()
        if old_hash == new_hash and not force:
            # No change, skip saving
            return "Success"
        # Save the new file
        with open(f"./staging/{key}", "wb") as file:
            file.write(response.content)
        metadata[key] = {"DateTimeUpdated": now_datetime, "hash": new_hash}

        # Trigger the preprocessing:
        self.logger.info(f"download_datasets:: Preprocessing dataset: {key}")

        # Preprocess the data
        res = self.data_preprocessor.preprocess_data(
            name=key,
            create_ds=True,
        )

        # Remove the file after preprocessing space
        self._remove_file(f"./staging/{key}")
        return res

    def _remove_file(self, file_path: str):
        """Removes a file if it exists.

        Args:
            file_path (str): The path to the file to remove.
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                self.logger.info(f"_remove_file:: Removed file: {file_path}")
        except Exception as e:
            self.logger.error(f"_remove_file:: Could not remove file {file_path}: {e}")

    @staticmethod
    def _json_safe(obj):
        """Return a version of obj, that is JSON serializable.

        Args:
            obj (Any): The object to convert.

        Returns:
            Any: The JSON serializable version of the object.
        """
        if isinstance(obj, (pd.Timestamp, datetime)):
            return obj.isoformat()
        elif isinstance(obj, (np.integer, np.int64)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64)):
            return float(obj)
        elif isinstance(obj, (np.ndarray, set)):
            return list(obj)
        elif pd.isna(obj):
            return None
        return obj
