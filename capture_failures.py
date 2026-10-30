"""Copy manually rejected captures and maintain an Excel-readable CSV ledger."""
import csv
import hashlib
import shutil
from pathlib import Path
from uuid import uuid4

from batch_state import atomic_json, fingerprint, read_json, timestamp

FOLDER = '拍摄失败'
REPORT = '拍摄失败记录.csv'


def csv_cell(value):
    text=str(value)
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) else text


class CaptureFailures:
    def __init__(self, destination):
        self.destination=Path(destination)
        self.path=self.destination/'capture_failures.json'
        self.data=read_json(self.path)
        if self.path.exists() and (not isinstance(self.data,dict) or self.data.get('schema')!=1
                                  or not isinstance(self.data.get('items'),dict)):
            raise ValueError('拍摄失败记录无法读取，请保留原文件 / Cannot read capture_failures.json; preserve the file.')
        self.data=self.data or dict(schema=1,items={})

    @staticmethod
    def key(source,digest):
        return hashlib.sha256((str(Path(source).resolve())+'\0'+digest).encode('utf-8')).hexdigest()

    def reject(self,source,name,digest,reason):
        source=Path(source)
        relative=Path(name)
        folder=self.destination/FOLDER
        target=folder/relative
        if relative.is_absolute() or '..' in relative.parts or not target.resolve().is_relative_to(folder.resolve()):
            raise ValueError('Invalid archive filename')
        if fingerprint(source)!=digest:
            raise ValueError('原照片已发生变化，请重新审核 / Source changed; review again before rejecting.')
        # A later capture may reuse the same filename. Never overwrite it.
        if target.exists() and fingerprint(target)!=digest:
            target=target.with_name(target.stem+'_'+digest+target.suffix)
        if target.exists() and fingerprint(target)!=digest:
            raise FileExistsError('归档文件冲突，请保留现有文件 / Archive conflict; preserve the existing file.')
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists():
            temporary=target.with_name(target.name+'.'+uuid4().hex+'.tmp')
            try:
                shutil.copy2(source,temporary)
                if fingerprint(temporary)!=digest:raise ValueError('Source changed during archiving')
                temporary.replace(target)
            finally:temporary.unlink(missing_ok=True)
        key=self.key(source,digest)
        previous=self.data['items'].get(key,{})
        self.data['items'][key]=dict(file=relative.as_posix(),source=str(source.resolve()),
            archive=target.relative_to(self.destination).as_posix(),sha256=digest,
            reason=reason,status='capture_failed',created_at=previous.get('created_at',timestamp()),updated_at=timestamp())
        self.persist()
        return target

    def resolved(self,source,digest):
        item=self.data['items'].get(self.key(source,digest))
        if item is not None:
            item.update(status='recropped',updated_at=timestamp())
            self.persist()

    def persist(self):
        atomic_json(self.path,self.data)
        self.write_report()

    def write_report(self):
        path=self.destination/REPORT
        temporary=path.with_name(path.name+'.tmp')
        try:
            with temporary.open('w',encoding='utf-8-sig',newline='') as stream:
                writer=csv.writer(stream)
                writer.writerow(['文件名 / File','原路径 / Source','归档路径 / Archive','原因 / Reason',
                                 '状态 / Status','首次记录时间 UTC / Created','更新时间 UTC / Updated','SHA256'])
                for row in self.data['items'].values():
                    state='已重新裁剪 / Re-cropped' if row['status']=='recropped' else '待重拍 / Retake'
                    writer.writerow(map(csv_cell,[row['file'],row['source'],row['archive'],row['reason'],state,
                                                  row['created_at'],row['updated_at'],row['sha256']]))
            temporary.replace(path)
        finally:temporary.unlink(missing_ok=True)
