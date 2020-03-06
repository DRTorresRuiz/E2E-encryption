import click

@click.group()
def cli():
  pass

@click.command()
@click.option('-g', '--greeting', 'greeting', required=True, type=str, show_default=True, default="Hi", help="The way you greet")
@click.option('-n', '--name', required=True, type=str, show_default=True, default="Siri", prompt="Your name")
def hello(greeting, name):
  """This script prints hello NAME."""
  click.echo("%s, %s!" % (greeting, name))

@click.command()
@click.option('-t', '--test', is_flag=True)
def test(test):
  """TEST!"""
  if ( test ):
    click.echo("This is also a test!")
  else:
    click.echo("This is a test!")


if __name__ == '__main__':
  
  cli.add_command(hello)
  cli.add_command(test)

  cli()