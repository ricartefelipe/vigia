terraform {
  required_version = ">= 1.6.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

resource "google_artifact_registry_repository" "vigia" {
  location      = var.region
  repository_id = "vigia"
  format        = "DOCKER"
}

resource "google_container_cluster" "vigia" {
  name                = "vigia"
  location            = var.region
  enable_autopilot    = true
  deletion_protection = false
}

resource "google_cloud_run_v2_service" "retrieval" {
  name     = "vigia-retrieval"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/vigia/vigia:latest"
      args  = ["retrieval"]
      ports {
        container_port = 8001
      }
      env {
        name  = "QDRANT_URL"
        value = var.qdrant_url
      }
      env {
        name  = "VIGIA_INGEST_ON_START"
        value = "1"
      }
      env {
        name  = "VIGIA_EMBEDDER"
        value = "vertex"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "true"
      }
    }
  }
}

resource "google_cloud_run_v2_service" "agentes" {
  name     = "vigia-agentes"
  location = var.region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/vigia/vigia:latest"
      args  = ["agentes"]
      ports {
        container_port = 8000
      }
      env {
        name  = "RETRIEVAL_URL"
        value = google_cloud_run_v2_service.retrieval.uri
      }
      env {
        name  = "A2A_URL"
        value = var.a2a_url
      }
      env {
        name  = "VIGIA_LLM"
        value = "gemini"
      }
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "true"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
    }
  }
}
