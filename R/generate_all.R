#!/usr/bin/env Rscript
# generate_all.R — Master script to regenerate all golden calibration files.
#
# Run from forgecal root:
#   Rscript R/generate_all.R
#
# Outputs:
#   golden/spc/r_reference.json
#   golden/stat/r_reference.json
#   golden/doe/r_reference.json
#   golden/rel/r_reference.json

cat("=== Forge Calibration: Generating R reference values ===\n\n")

# Resolve script directory robustly
args <- commandArgs(trailingOnly = FALSE)
file_arg <- grep("--file=", args, value = TRUE)
if (length(file_arg) > 0) {
  script_dir <- dirname(normalizePath(sub("--file=", "", file_arg[1])))
} else {
  script_dir <- getwd()
}

# Set global dir for helpers.R and all sub-scripts
.forgecal_r_dir <<- script_dir

# Load helpers first (sets .forgecal_root)
source(file.path(script_dir, "helpers.R"))

# Each script is independent — run them in sequence
scripts <- c("cal_spc.R", "cal_stat.R", "cal_doe.R", "cal_rel.R")

for (s in scripts) {
  cat(sprintf("Running %s...\n", s))
  tryCatch({
    source(file.path(script_dir, s), local = FALSE)
  }, error = function(e) {
    cat(sprintf("  ERROR in %s: %s\n", s, conditionMessage(e)))
  })
  cat("\n")
}

cat("=== All reference files generated ===\n")
