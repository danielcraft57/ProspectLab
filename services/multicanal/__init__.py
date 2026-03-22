"""
Service multicanal pour orchestrer les messages sortants.

Ce package fournit une base simple pour brancher plusieurs canaux
(email, linkedin, facebook, instagram, etc.) avec une interface unique.
"""

from .campaign import CampaignAttempt, CampaignReport, SocialCampaignRunner
from .dispatcher import MultiCanalService
from .providers import DummyProvider, MetaMessengerProvider, XDirectMessageProvider
from .types import ChannelName, MessagePayload, SendResult

__all__ = [
    "ChannelName",
    "MessagePayload",
    "SendResult",
    "MultiCanalService",
    "DummyProvider",
    "MetaMessengerProvider",
    "XDirectMessageProvider",
    "CampaignAttempt",
    "CampaignReport",
    "SocialCampaignRunner",
]

