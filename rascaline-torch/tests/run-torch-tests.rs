use std::path::PathBuf;

mod utils;

#[test]
fn run_torch_tests() {
    if cfg!(tarpaulin) {
        // do not run this test when collecting Rust coverage
        return;
    }

    const CARGO_TARGET_TMPDIR: &str = env!("CARGO_TARGET_TMPDIR");

    // ====================================================================== //
    // setup dependencies for the torch tests

    let mut build_dir = PathBuf::from(CARGO_TARGET_TMPDIR);
    build_dir.push("torch-tests");
    let deps_dir = build_dir.join("deps");

    let rascaline_dep = deps_dir.join("rascaline");
    std::fs::create_dir_all(&rascaline_dep).expect("failed to create rascaline dep dir");
    let rascaline_cmake_prefix = utils::setup_rascaline(rascaline_dep);

    let torch_dep = deps_dir.join("torch");
    std::fs::create_dir_all(&torch_dep).expect("failed to create torch dep dir");
    let pytorch_cmake_prefix = utils::setup_pytorch(torch_dep);

    // ====================================================================== //
    // build the rascaline-torch C++ tests and run them
    let mut source_dir = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap());
    source_dir.extend(["..", "rascaline-torch"]);

    // configure cmake for the tests
    let mut cmake_config = utils::cmake_config(&source_dir, &build_dir);
    cmake_config.arg("-DRASCALINE_TORCH_TESTS=ON");
    cmake_config.arg("-DRASCALINE_TORCH_FETCH_METATENSOR_TORCH=ON");
    cmake_config.arg(format!(
        "-DCMAKE_PREFIX_PATH={};{}",
        rascaline_cmake_prefix.display(),
        pytorch_cmake_prefix.display()
    ));
    let status = cmake_config.status().expect("could not run cmake");
    assert!(status.success(), "failed to run torch tests cmake configuration");

    // build the tests with cmake
    let mut cmake_build = utils::cmake_build(&build_dir);
    let status = cmake_build.status().expect("could not run cmake");
    assert!(status.success(), "failed to run torch tests cmake build");

    // run the tests
    let mut ctest = utils::ctest(&build_dir);
    let status = ctest.status().expect("could not run ctest");
    assert!(status.success(), "failed to run running torch tests");
}
