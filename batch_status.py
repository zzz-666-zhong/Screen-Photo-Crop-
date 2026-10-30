"""Read-only view of batch progress and result files."""
from pathlib import Path


def existing_crops(destination, names):
    """Find actual output PNGs, retaining paths relative to the input folder."""
    root=Path(destination)/'裁剪成功'
    if not root.is_dir():
        return set()
    wanted=set(names)
    suffix='_cropped.png'
    found=set()
    for path in root.rglob('*_cropped.png'):
        if path.is_file():
            relative=path.relative_to(root)
            source=relative.with_name(relative.name[:-len(suffix)]).as_posix()
            if source in wanted:
                found.add(source)
    return found


def image_state(session,index,saved):
    name=session.names[index]
    record=session.records.get(name,{})
    state=record.get('status')
    cropped=name in saved
    if name in session.drafts:
        return 'saved_draft' if cropped else 'draft'
    if state=='capture_failed':
        return 'saved_capture_failed' if cropped else 'capture_failed'
    if state=='error':
        return 'saved_error' if cropped else 'error'
    if state=='skipped':
        return 'saved_skipped' if cropped else 'skipped'
    if cropped:
        return 'saved'
    if state in ('ok','existing'):
        return 'missing'
    return 'pending'


def matches_filter(session,index,saved,choice):
    name=session.names[index]
    if choice=='uncropped':return name not in saved
    if choice=='cropped':return name in saved
    if choice=='pending':return session.pending(index)
    if choice=='skipped':return session.records.get(name,{}).get('status')=='skipped'
    if choice=='error':return session.records.get(name,{}).get('status')=='error'
    if choice=='capture_failed':return session.records.get(name,{}).get('status')=='capture_failed'
    return True


def progress_summary(session,saved):
    names=set(session.names)
    cropped=len(names.intersection(saved))
    total=len(session.names)
    processed=sum(not session.pending(i) for i in range(total))
    skipped=sum(session.records.get(n,{}).get('status')=='skipped' for n in session.names)
    errors=sum(session.records.get(n,{}).get('status')=='error' for n in session.names)
    rejected=sum(session.records.get(n,{}).get('status')=='capture_failed' for n in session.names)
    drafts=len(names.intersection(session.drafts))
    return dict(total=total,cropped=cropped,uncropped=total-cropped,processed=processed,
                skipped=skipped,errors=errors,drafts=drafts,capture_failed=rejected)
