# helpers.R — shared utilities for forge calibration R scripts
#
# Each cal_*.R script sources this, then writes golden JSON.

library(jsonlite)

# Resolve the R/ directory — set by generate_all.R or fallback
if (!exists(".forgecal_r_dir")) {
  args <- commandArgs(trailingOnly = FALSE)
  file_arg <- grep("--file=", args, value = TRUE)
  if (length(file_arg) > 0) {
    .forgecal_r_dir <- dirname(normalizePath(sub("--file=", "", file_arg[1])))
  } else {
    .forgecal_r_dir <- getwd()
  }
}
.forgecal_root <- dirname(.forgecal_r_dir)

write_golden <- function(cases, outfile) {
  # Write list of calibration cases to JSON
  json <- toJSON(cases, auto_unbox = TRUE, digits = 10, pretty = TRUE)
  writeLines(json, outfile)
  cat(sprintf("  wrote %s (%d cases)\n", outfile, length(cases)))
}

make_case <- function(case_id, description, package, category,
                      data = list(), config = list(),
                      expectations = list()) {
  list(
    case_id     = case_id,
    description = description,
    package     = package,
    category    = category,
    data        = data,
    config      = config,
    expectations = expectations
  )
}

expect_numeric <- function(key, value, tolerance = 0.001) {
  list(key = key, expected = value, tolerance = tolerance, comparison = "abs_within")
}

expect_rel <- function(key, value, tolerance = 0.01) {
  list(key = key, expected = value, tolerance = tolerance, comparison = "rel_within")
}

expect_gt <- function(key, value) {
  list(key = key, expected = value, tolerance = 0, comparison = "greater_than")
}

expect_lt <- function(key, value) {
  list(key = key, expected = value, tolerance = 0, comparison = "less_than")
}

expect_equals <- function(key, value) {
  list(key = key, expected = value, tolerance = 0, comparison = "equals")
}

expect_between <- function(key, lo, hi) {
  list(key = key, expected = c(lo, hi), tolerance = 0, comparison = "between")
}
