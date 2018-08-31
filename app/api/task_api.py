from app import apfell, db_objects
from sanic.response import json
from app.database_models.model import Callback, Operator, Task
from urllib.parse import unquote_plus
import datetime
from sanic_jwt.decorators import protected, inject_user


# This gets all tasks in the database
@apfell.route(apfell.config['API_BASE'] + "/tasks/", methods=['GET'])
@inject_user()
@protected()
async def get_all_tasks(request, user):
    callbacks = Callback.select()
    operators = Operator.select()
    tasks = Task.select()
    # callbacks_with_operators = await db_objects.prefetch(callbacks, operators)
    full_task_data = await db_objects.prefetch(tasks, callbacks, operators)
    return json([c.to_json() for c in full_task_data])


@apfell.route(apfell.config['API_BASE'] + "/tasks/callback/<cid:int>", methods=['GET'])
@inject_user()
@protected()
async def get_all_tasks_for_callback(request, cid, user):
    try:
        callback = await db_objects.get(Callback, id=cid)
    except Exception as e:
        return json({'status': 'error',
                     'error': 'Callback does not exist'})
    try:
        tasks = Task.select()
        cb_task_data = await db_objects.execute(Task.select().where(Task.callback == callback))
        return json([c.to_json() for c in cb_task_data])
    except Exception as e:
        return json({'status': 'error',
                     'error': 'No Tasks',
                     'msg': str(e)})


# We don't put @protected or @inject_user here since the callback needs to be able to call this function
@apfell.route(apfell.config['API_BASE'] + "/tasks/callback/<cid:int>/nextTask", methods=['GET'])
async def get_next_task(request, cid, user):
    # gets the next task by time for the callback to do
    try:
        callback = await db_objects.get(Callback, id=cid)
    except Exception as e:
        return json({'status': 'error',
                     'error': 'callback does not exist'})
    try:
        callback.last_checkin = datetime.datetime.now()
        callback.active = True  # always set this to true regardless of what it was before because it's clearly active
        await db_objects.update(callback)  # update the last checkin time
        tasks = await db_objects.get(Task.select().join(Callback).where(
            (Task.callback == callback) & (Task.status == "submitted")).order_by(Task.timestamp))
    except Exception as e:
        print(e)
        return json({'command': 'none'})  # return empty if there are no tasks that meet the criteria
    tasks.status = "processing"
    await db_objects.update(tasks)
    return json({"command": tasks.command, "params": tasks.params, "id": tasks.id})


# create a new task to a specific callback
@apfell.route(apfell.config['API_BASE'] + "/tasks/callback/<cid:int>/operator/<name:string>", methods=['POST'])
@inject_user()
@protected()
async def add_task_to_callback(request, cid, name, user):
    name = unquote_plus(name)
    data = request.json
    print(data)
    return json(await add_task_to_callback_func(data, cid, name))


async def add_task_to_callback_func(data, cid, name):
    try:
        # first see if the operator and callback exists
        op = await db_objects.get(Operator, username=name)
        cb = await db_objects.get(Callback, id=cid)
        # now check the task and add it if it's valid
        # some tasks require a bit more processing, so we'll handle that here so it's easier for the implant
        task = await db_objects.create(Task, callback=cb, operator=op, command=data['command'], params=data['params'])
        return {'status': 'success'}
    except Exception as e:
        return {'status': 'error', 'error': 'Failed to create task',  'msg': str(e)}
