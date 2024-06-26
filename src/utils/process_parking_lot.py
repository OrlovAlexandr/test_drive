from typing import Any

import cv2
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN


def get_parking_spaces(df: pd.DataFrame, eps: float = 15, threshold: float = 0.9,
                       space_size: float = 0.5) -> tuple[Any, bool]:
    """
    Get parking spaces with each radius based on the bbox size

    Args:
        df (pd.DataFrame): DataFrame with detections
        eps (float, optional): Maximum distance between two samples for DBSCAN clustering.
        threshold (float, optional): Threshold for filtering clusters.
        space_size (float, optional): Size of the parking space, calculated as a fraction of the bbox minimum side.

    Returns:
        median_coords (pd.DataFrame): DataFrame with median coordinates of each parking space
    """

    # Point coordinates
    coords = df[['cx', 'cy']].values

    # Clustering with DBSCAN
    db = DBSCAN(eps=eps, min_samples=2).fit(coords)

    # Adding cluster labels to DataFrame
    df['cluster'] = db.labels_

    # Number of frames where each cluster appears
    total_frames = df['timestamp'].nunique()

    # Setting threshold
    threshold = total_frames * threshold

    # Calculate number of frames for each cluster
    cluster_counts = df.groupby('cluster')['timestamp'].nunique()

    # Filter clusters with less than the threshold
    valid_clusters = cluster_counts[cluster_counts >= threshold].index

    # Filter DataFrame with valid clusters
    df_filtered = df[df['cluster'].isin(valid_clusters)]
    df_filtered = df_filtered.copy()
    # print(df_filtered.head(50))
    df_filtered['width'] = df_filtered['x2'] - df_filtered['x1']
    df_filtered['height'] = df_filtered['y2'] - df_filtered['y1']

    # Calculate median coordinates
    median_centers = df_filtered.groupby('cluster')[['cx', 'cy']].median().reset_index()
    median_width = df_filtered.groupby('cluster')['width'].median().reset_index()
    median_height = df_filtered.groupby('cluster')['height'].median().reset_index()
    # Get min side of the bbox and calculate radius
    sides = pd.merge(median_width, median_height, on='cluster')
    sides['min_side'] = sides.apply(lambda x: x['width'] if x['width'] < x['height'] else x['height'], axis=1)
    sides['radius'] = sides['min_side'] * (space_size / 2)
    # Concatenate median coordinates with radius
    median_coords = pd.concat([median_centers, sides['radius']], axis=1)
    median_coords = median_coords[['cx', 'cy', 'radius']].reset_index(drop=True)

    return median_coords


def calc_crop_from_vertices(vertices: list=None, padding: int = 50, video_path: str = '') -> list:
    """
    Calculate the crop region from a list of vertices.

    Args:
        vertices (list): A list of vertices of the polygon.
        padding (int): The padding to be applied around the vertices to create the crop region.
            Default is 50.
        video_path (str): The path to the video file. Default is an empty string.

    Returns:
        crop (list): A list representing the crop region in XYXY format.
    """
    if vertices is not None:
        x = np.array(vertices)[:, 0]
        y = np.array(vertices)[:, 1]
        crop = [x.min() - padding, y.min() - padding, x.max() + padding, y.max() + padding]

        cap = cv2.VideoCapture(video_path)  # Read video with OpenCV
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()

        crop = np.clip(crop, 0, [width, height, width, height]).tolist()
    else:
        crop = []

    return crop


def get_order(parking_spaces: pd.DataFrame) -> bool:
    """
    Args:
        parking_spaces (pd.DataFrame): DataFrame with median coordinates of each parking space
    Returns:
        order_left_right (bool): "True" if left-to-right, "False" if bottom-to-top
    """
    spaces_width = parking_spaces['cx'].max() - parking_spaces['cx'].min()
    spaces_height = parking_spaces['cy'].max() - parking_spaces['cy'].min()
    order_left_right = True if spaces_width > spaces_height else False
    return order_left_right


def apply_order(parking_spaces: pd.DataFrame, order_left_right: bool = True) -> pd.DataFrame:
    """
    Args:
        parking_spaces (pd.DataFrame): DataFrame with median coordinates of each parking space
        order_left_right (bool): "True" if left-to-right, "False" if bottom-to-top
    Returns:
        parking_spaces (pd.DataFrame): DataFrame with sorted order of each parking space
    """
    if order_left_right:
        parking_spaces = parking_spaces.sort_values(by='cx').reset_index(drop=True)
    else:
        parking_spaces = parking_spaces.sort_values(by='cy', ascending=False).reset_index(drop=True)
    parking_spaces = parking_spaces.reset_index(names='space')
    return parking_spaces
