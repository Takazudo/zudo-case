"""Exercise the actual current/R7 viewer in Chromium, including both renderers.

No CAD, printer, publication or supplier operations are performed. A browser
launch failure is a failed check, never substituted by a software-render pass.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os

from playwright.sync_api import sync_playwright


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def checked_snapshot(page):
    return page.evaluate("""() => {
      const s=window.tenboxStudy;
      return {view:s.state.view,revision:s.state.revision,camera:s.camera,
              renderer:s.renderer,frames:s.frames,visible:s.visibleParts().length};
    }""")


def check_lid_geometry(page):
    """Check material presence in the actual decoded, world-placed browser mesh.

    Sample the former gaps on both panels, rather than trusting a revision label,
    bounding box, thumbnail or a list of changed mesh names. Rays start inside
    each probe volume and point toward the interior of the case. Deduplicate
    coplanar triangle hits so a triangulation seam cannot double the parity.
    """
    result = page.evaluate("""() => {
      const d=window.tenboxStudy.DATA;
      const sub=(a,b)=>a.map((x,i)=>x-b[i]);
      const dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0);
      const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
      function inside(parts,id,point,direction){
        const part=parts.find(p=>(p.sourceId||p.id)===id);
        if(!part)throw Error('Missing browser part '+id);
        const mesh=d.meshes[part.mesh],o=sub(point,part.staticOffset||[0,0,0]),hits=[];
        for(let k=0;k<mesh.i.length;k+=3){
          const [a,b,c]=mesh.i.slice(k,k+3).map(i=>mesh.p.slice(i*3,i*3+3));
          const e1=sub(b,a),e2=sub(c,a),h=cross(direction,e2),det=dot(e1,h);
          if(Math.abs(det)<1e-10)continue;
          const s=sub(o,a),u=dot(s,h)/det;
          if(u< -1e-8||u>1+1e-8)continue;
          const q=cross(s,e1),v=dot(direction,q)/det;
          if(v< -1e-8||u+v>1+1e-8)continue;
          const t=dot(e2,q)/det;
          if(t>1e-7)hits.push(t);
        }
        hits.sort((a,b)=>a-b);
        return hits.filter((t,i)=>!i||Math.abs(t-hits[i-1])>1e-6).length%2===1;
      }
      const gaps=[],windows=[],retained=[];
      for(const id of ['lid-front','lid-back']){
        const sign=id==='lid-front'?1:-1;
        const probe=(x,z)=>[sign*x,sign*-143.5,z];
        const direction=[0,sign,0];
        for(const x of [-28,-18,-8,8,18,29])for(const z of [103.5,105.5,107.3]){
          const point=probe(x,z);
          gaps.push({id,point,current:inside(d.parts,id,point,direction),previous:inside(d.baselineParts,id,point,direction)});
        }
        for(const x of [-120,120]){
          const point=probe(x,105.5);
          windows.push({id,point,current:inside(d.parts,id,point,direction),previous:inside(d.baselineParts,id,point,direction)});
        }
        for(const x of [-60,0,60]){
          const point=probe(x,105.5);
          retained.push({id,point,current:inside(d.parts,id,point,direction),previous:inside(d.baselineParts,id,point,direction)});
        }
      }
      return {method:'Ray parity in decoded browser triangles at their actual world placements',revision:d.revision,gaps,windows,retained};
    }""")
    require(result["revision"] == "R8-LID-LEDGE-01", "Wrong actual model revision")
    require(len(result["gaps"]) == 36 and all(r["current"] and not r["previous"] for r in result["gaps"]),
            "The browser meshes do not fill both former centre gaps on both lid panels")
    require(all(not r["current"] and not r["previous"] for r in result["windows"]),
            "An outer bracket opening was filled in the browser model")
    require(all(r["current"] and r["previous"] for r in result["retained"]),
            "An original retaining ledge disappeared from the browser model")
    result["passed"] = True
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preview", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--browser-executable", default=os.environ.get("BROWSER_EXECUTABLE"))
    args = ap.parse_args()
    preview, out = args.preview.resolve(), args.out.resolve()
    require(preview.is_file(), f"Missing current preview: {preview}")
    require(not out.exists(), f"Existing evidence preserved: {out}")
    out.mkdir(parents=True)
    report = {"preview": preview.name,
              "preview_sha256": hashlib.sha256(preview.read_bytes()).hexdigest(),
              "scope": "Actual Chromium rendering and DOM interactions for the R8-LID-LEDGE-01 viewer; not physical validation.",
              "passed": False, "runs": []}
    try:
        with sync_playwright() as pw:
            launch = {"headless": True, "args": ["--no-sandbox", "--disable-dev-shm-usage",
                      "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]}
            if args.browser_executable:
                launch["executable_path"] = args.browser_executable
            browser = pw.chromium.launch(**launch)
            report["browser_version"] = browser.version
            for renderer in ["canvas", "webgl"]:
                errors = []
                context = browser.new_context(viewport={"width": 1280, "height": 1050}, device_scale_factor=1)
                page = context.new_page()
                page.on("pageerror", lambda err: errors.append(str(err)))
                page.goto(preview.as_uri() + "?renderer=" + renderer, wait_until="load")
                page.wait_for_selector('#tenbox-v2-r8-lid-ledge-01[data-ready="true"]', timeout=120000)
                initial = checked_snapshot(page)
                require(initial["renderer"] == renderer, f"Requested {renderer}, got {initial['renderer']}")
                require(initial["revision"] == "R8-LID-LEDGE-01" and initial["visible"] > 100, "Incomplete initial current assembly")
                lid_geometry = check_lid_geometry(page)
                geometry = page.evaluate("""() => {
                  const s=window.tenboxStudy,d=s.DATA;
                  const bounds=p=>p.box.map((v,i)=>v+(p.staticOffset?.[i%3]||0));
                  const key=p=>(p.sourceId||p.id).replace(/^r[78]-rail-/,'rail-');
                  const old=new Map(d.baselineParts.map(p=>[key(p),p]));
                  const fixed=[],moving=[];
                  for(const p of d.parts){
                    const q=old.get(key(p));if(!q)continue;
                    const a=bounds(p),b=bounds(q),delta=a.map((x,i)=>x-b[i]);
                    if(/^r[78]-rail-/.test(p.id))moving.push({id:p.id,delta});
                    if(/^(body-|lid-|spacer-|rail-bolt-|rail-washer-|rail-nut-)/.test(p.id))fixed.push({id:p.id,delta});
                  }
                  return {fixed,moving,currentParts:d.parts.length,baselineParts:d.baselineParts.length,
                    sourceModelSha256:d.previewMetadata.sourceModelSha256,
                    triangleIndicesPreserved:d.previewMetadata.meshIdentity.triangleIndicesPreserved};
                }""")
                require(geometry["currentParts"] == geometry["baselineParts"], "R7 comparison inventory changed")
                require(geometry["triangleIndicesPreserved"], "Display topology changed")
                require(len(geometry["fixed"]) >= 40, "Missing fixed enclosure/mounting comparison")
                require(geometry["moving"], "Missing frame / rail comparison")
                require(all(max(abs(x) for x in r["delta"]) < .00101 for r in geometry["fixed"]),
                        "Case, lid, spacers or mounting hardware moved in the preview")
                for row in geometry["moving"]:
                    expected = [0, 0, 12.631103, 0, 0, 12.631103]
                    require(max(abs(a-b) for a, b in zip(row["delta"], expected)) < .00101,
                            "Incorrect frame displacement: " + row["id"])

                inspected = []
                for view in ["lower-slot", "rail-junction", "side-fixings", "side-fixing", "inside-nuts", "side", "underside", "lid-fit", "lid-ledge"]:
                    page.locator(f'[data-view="{view}"]').click()
                    page.wait_for_function("v => window.tenboxStudy.state.view===v", arg=view)
                    snapshot = checked_snapshot(page)
                    require(snapshot["visible"] > 0, f"Empty {view} scene")
                    inspected.append(snapshot)

                page.locator('[data-view="lid-ledge"]').click()
                page.evaluate("window.tenboxStudy.render()")
                ledge_current = checked_snapshot(page)
                require(ledge_current["visible"] == 1, "Lid ledge detail must isolate the actual panel")
                require("connected" in page.locator('[data-id="stageDetail"]').inner_text(), "Wrong current ledge label")
                page.locator('[data-id="stage"]').screenshot(path=str(out / f"{renderer}-lid-ledge-current.png"))
                page.locator('[data-revision="R7"]').click()
                page.evaluate("window.tenboxStudy.render()")
                require(checked_snapshot(page)["camera"] == ledge_current["camera"], "Lid comparison moved camera")
                require("two centre gaps" in page.locator('[data-id="stageDetail"]').inner_text(), "Wrong previous ledge label")
                page.locator('[data-id="stage"]').screenshot(path=str(out / f"{renderer}-lid-ledge-r7.png"))
                page.locator('[data-revision="R8-LID-LEDGE-01"]').click()

                page.locator('[data-view="lower-slot"]').click()
                page.evaluate("window.tenboxStudy.render()")
                r8 = checked_snapshot(page)
                page.locator('[data-id="stage"]').screenshot(path=str(out / f"{renderer}-lower-slot-r8.png"))
                page.locator('[data-revision="R7"]').click()
                page.evaluate("window.tenboxStudy.render()")
                r7 = checked_snapshot(page)
                require(r7["camera"] == r8["camera"], "Revision switch moved the camera")
                require(r7["revision"] == "R7", "R7 comparison did not activate")
                require("Upper slots" in page.locator('[data-id="stageDetail"]').inner_text(), "Wrong R7 slot label")
                page.locator('[data-id="stage"]').screenshot(path=str(out / f"{renderer}-lower-slot-r7.png"))
                require((out / f"{renderer}-lower-slot-r8.png").read_bytes() !=
                        (out / f"{renderer}-lower-slot-r7.png").read_bytes(), "Comparison rendered identical views")
                page.locator('[data-revision="R8-LID-LEDGE-01"]').click()
                require(checked_snapshot(page)["camera"] == r8["camera"], "Return to current revision moved the camera")
                page.locator('[data-view="lid-fit"]').click()
                page.evaluate("window.tenboxStudy.render()")
                detail = page.locator('[data-id="stageDetail"]').inner_text()
                require("19.869" in detail and "7.131" in detail, "Lid capacity / shortfall missing")
                require(page.locator('[data-id="lidDimension"]').is_visible(), "Missing lid dimension overlay")
                page.locator('[data-id="stage"]').screenshot(path=str(out / f"{renderer}-lid-fit.png"))

                page.locator('[data-view="assembly"]').click()
                before = checked_snapshot(page)["visible"]
                page.locator('[data-id="rails"]').uncheck()
                require(checked_snapshot(page)["visible"] < before, "Frame visibility control failed")
                page.locator('[data-id="rails"]').check()
                page.locator('[data-id="separate"]').click()
                require(page.evaluate("window.tenboxStudy.state.explode") == 25, "Separation control failed")
                page.locator('[data-id="assembled"]').click()
                page.locator('[data-id="lid"]').check()
                closed_lid = page.evaluate("""() => window.tenboxStudy.visibleParts()
                  .filter(p=>['lid-front','lid-back'].includes(p.sourceId||p.id))
                  .map(p=>({id:p.sourceId||p.id,mesh:p.mesh,offset:window.tenboxStudy.partOffset(p)}))""")
                require(len(closed_lid) == 2, "Closed assembly must use both corrected lid panels")
                page.locator('[data-id="lidlift"]').evaluate("el => el.value = '45'")
                page.locator('[data-id="lidlift"]').dispatch_event("input")
                require(page.evaluate("window.tenboxStudy.state.lidLift") == 45, "Lid lift control failed")
                lifted_lid = page.evaluate("""() => window.tenboxStudy.visibleParts()
                  .filter(p=>['lid-front','lid-back'].includes(p.sourceId||p.id))
                  .map(p=>({id:p.sourceId||p.id,mesh:p.mesh,offset:window.tenboxStudy.partOffset(p)}))""")
                require(all(a["id"] == b["id"] and a["mesh"] == b["mesh"] and
                            max(abs(b["offset"][i]-a["offset"][i]-(45 if i == 2 else 0)) for i in range(3)) < 1e-7
                            for a,b in zip(closed_lid,lifted_lid)), "Lid lift replaced or moved corrected geometry incorrectly")
                page.locator('[data-id="separate"]').click()
                exploded_ids = page.evaluate("""() => window.tenboxStudy.visibleParts()
                  .filter(p=>['lid-front','lid-back'].includes(p.sourceId||p.id)).map(p=>p.mesh)""")
                require(exploded_ids == [p["mesh"] for p in closed_lid], "Exploded assembly substituted old lid geometry")
                page.locator('[data-id="stage"]').screenshot(path=str(out / f"{renderer}-lifted-separated-lid.png"))
                page.locator('[data-id="assembled"]').click()
                page.locator('[data-id="part"]').select_option("body-right")
                require(checked_snapshot(page)["visible"] == 1, "Part inspector did not isolate a part")
                page.locator('[data-view="assembly"]').click()
                page.locator('[data-id="stage"]').screenshot(path=str(out / f"{renderer}-assembly.png"))
                canvas = page.locator('[data-id="canvas"]')
                box = canvas.bounding_box()
                camera_before = checked_snapshot(page)["camera"]
                page.mouse.move(box["x"] + box["width"]*.55, box["y"] + box["height"]*.55)
                page.mouse.down()
                page.mouse.move(box["x"] + box["width"]*.55 + 50, box["y"] + box["height"]*.55 + 25, steps=4)
                page.mouse.up()
                require(checked_snapshot(page)["camera"] != camera_before, "Orbit gesture failed")

                mobile = []
                for width in [736, 390, 320]:
                    page.set_viewport_size({"width": width, "height": 1000})
                    page.locator('[data-view="lower-slot"]').click()
                    layout = page.evaluate("""() => {
                      const root=document.getElementById('tenbox-v2-r8-lid-ledge-01');
                      return {viewport:innerWidth,scroll:document.documentElement.scrollWidth,
                              rootWidth:root.getBoundingClientRect().width,
                              canvasWidth:root.querySelector('canvas').getBoundingClientRect().width};
                    }""")
                    require(layout["scroll"] <= width+1 and layout["canvasWidth"] > 200, "Responsive layout overflows")
                    mobile.append(layout)
                    if width == 390:
                        page.screenshot(path=str(out / f"{renderer}-mobile.png"), full_page=True)
                        page.locator('[data-view="lid-ledge"]').click()
                        page.evaluate("window.tenboxStudy.render()")
                        require(checked_snapshot(page)["visible"] == 1, "Mobile lid detail is empty")
                        page.screenshot(path=str(out / f"{renderer}-mobile-lid-ledge.png"), full_page=True)
                require(not errors, "Browser JavaScript errors: " + "; ".join(errors))
                report["runs"].append({"renderer": renderer, "initial": initial, "geometry": geometry,
                                        "lid_geometry": lid_geometry, "closed_lid": closed_lid,
                                        "lifted_lid": lifted_lid, "exploded_lid_meshes": exploded_ids,
                                        "views": inspected, "same_camera_comparison": True,
                                        "responsive_widths": mobile, "errors": errors, "passed": True})
                context.close()
            browser.close()
        report["passed"] = True
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        (out / "browser-report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "renderers": [r["renderer"] for r in report["runs"]],
                      "browser_version": report["browser_version"], "report": str(out / "browser-report.json")}))


if __name__ == "__main__":
    main()
