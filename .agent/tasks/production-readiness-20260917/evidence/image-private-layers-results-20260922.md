# Pinned-image private-layer inspection — 22 September 2026

This evidence concerns only the pinned local Linux/arm64 image
`sha256:9d6edac8b6948e239c0bab54564f92f829e5b9dfc93f3ca0626060ffb4e60853`
and frozen source `99849935de26e2932613f2a73cf515dff49104a1`. Independent
pre-execution, runtime and byte-preserved package reviews passed.

## Captured result and integrity chain

The controller read all 20 OCI layers without extracting or running image
files. It measured 61,500 regular entries, 2,866,391,223 regular-file bytes,
2,919,512,576 expanded bytes, and a 1,074,089,472-byte archive in 15.528
seconds. It verified the image/archive descriptors, blob identities, layer
order, and config diff-ID chain before and after inspection. The raw layout
and descriptor captures preserve the archive-side evidence.

The actual scan reported zero private-path-family findings and zero total
runtime findings. Its narrow scanner covers enumerated private artifact path
families beneath `/app` plus one known exact 297,147-byte Google Docs response
digest at any path; it checks links without following them and scans earlier
deleted layers as well. The known digest is a detection rule, not a runtime
finding in this image.

The first controls capture passed in 194.197 ms. The final controls v2 capture
passed in 158.561 ms and is the current frozen helper/checks proof. Controls
v1 is retained as raw history, but the exact helper bytes used before the v2
additional checks were not archived; it is therefore not current frozen
runtime proof.

## Scope limitations

This is not a general credential scanner and does not establish that every
private variant is absent. It does not inspect the broader build context,
other/older images, or provide general credential proof. Consequently
`SEC-BUILD-CONTEXT-02` remains open and this result must not be promoted to a
whole-image-clean claim. No files were extracted and no containers, images or
volumes were created or removed. No product change, provider call or production
change was performed.

## Canonical raw artifacts

`image-private-layers-hflypi-20260922/` contains five byte-preserved raw
captures: archive layout, archive descriptors, controls v1, controls v2, and
the all-layer scan result. `SHA256SUMS` binds those captures to the current
two scanner/checks files.
