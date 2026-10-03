output "cluster" {
  value = google_container_cluster.vigia.name
}

output "retrieval_uri" {
  value = google_cloud_run_v2_service.retrieval.uri
}

output "agentes_uri" {
  value = google_cloud_run_v2_service.agentes.uri
}
