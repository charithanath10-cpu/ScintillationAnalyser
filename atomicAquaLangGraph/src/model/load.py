from langchain_aws import ChatBedrock
import os
import boto3

def load_model() -> ChatBedrock:
    """
    Get Bedrock model client with optimized settings.
    Uses IAM authentication via AWS credentials.
    
    Reads BEDROCK_MODEL_ID from environment variable.
    Default: us.anthropic.claude-sonnet-4-6
    """
    # Read model ID at runtime (not at import time)
    model_id = os.getenv("BEDROCK_MODEL_ID", "us.anthropic.claude-sonnet-4-6")
    
    print(f"[MODEL] Loading Bedrock model: {model_id}")
    
    # Try to get credentials from Streamlit secrets first (for cloud deployment)
    try:
        import streamlit as st
        # Only use Streamlit secrets if they contain real credentials (not placeholders)
        if ("AWS_ACCESS_KEY_ID" in st.secrets and 
            st.secrets["AWS_ACCESS_KEY_ID"] != "your-access-key-here" and
            len(st.secrets["AWS_ACCESS_KEY_ID"]) > 10):
            
            print("[MODEL] Using Streamlit secrets for AWS credentials")
            # Create a boto3 session with explicit credentials
            session = boto3.Session(
                aws_access_key_id=st.secrets["AWS_ACCESS_KEY_ID"],
                aws_secret_access_key=st.secrets["AWS_SECRET_ACCESS_KEY"],
                region_name="us-east-1"
            )
            client = session.client("bedrock-runtime")
            
            return ChatBedrock(
                model_id=model_id,
                client=client,
                model_kwargs={
                    "temperature": 0.0,
                    "max_tokens": 2000,
                },
                streaming=True,
            )
    except (FileNotFoundError, KeyError, ImportError, AttributeError):
        pass
    
    # Fall back to default AWS credentials (from aws configure, environment, or IAM role)
    print("[MODEL] Using default AWS credentials (from aws configure or environment)")
    
    # Create boto3 client explicitly to ensure credentials are picked up correctly
    bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")
    
    return ChatBedrock(
        model_id=model_id,
        client=bedrock_client,  # Pass explicit client instead of letting LangChain create it
        model_kwargs={
            "temperature": 0.0,
            "max_tokens": 2000,
        },
        streaming=True,
    )