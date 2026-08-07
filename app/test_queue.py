from services.render_queue import RenderQueue

queue = RenderQueue()

queue.add_job("Scene01")
queue.add_job("Scene02")
queue.add_job("Scene03")

job = queue.next_job()

print(job)

queue.complete(job)

print("Waiting:", len(queue.waiting_jobs()))
print("Completed:", len(queue.completed_jobs()))